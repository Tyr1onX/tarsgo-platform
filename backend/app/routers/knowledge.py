import logging
import os

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, load_only

from ..auth import require_admin
from ..db import get_db
from ..knowledge import (
    KnowledgeConfigError,
    KnowledgeSourceError,
    MAX_UPLOAD_BYTES,
    UploadRejected,
    create_uploaded_document,
    delete_document,
    knowledge_enabled,
    sync_github_documents,
)
from ..models import KnowledgeDocument, Member
from ..schemas import KnowledgeDocumentOut, KnowledgeOptionOut, KnowledgeSyncOut


router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])
logger = logging.getLogger(__name__)


def _document_output(document: KnowledgeDocument) -> dict:
    return {
        "id": document.id,
        "source_type": document.source_type,
        "source_name": document.source_name,
        "display_name": document.source_path if document.source_type == "github" else document.source_name,
        "title": document.title,
        "parse_status": document.parse_status,
        "parse_error": document.parse_error,
        "is_active": document.is_active,
        "synced_at": document.synced_at,
        "source_updated_at": document.source_updated_at,
    }


@router.get("", response_model=list[KnowledgeDocumentOut])
def list_documents(
    current: Member = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[dict]:
    documents = db.scalars(
        select(KnowledgeDocument)
        .options(load_only(
            KnowledgeDocument.id,
            KnowledgeDocument.source_type,
            KnowledgeDocument.source_name,
            KnowledgeDocument.source_path,
            KnowledgeDocument.title,
            KnowledgeDocument.parse_status,
            KnowledgeDocument.parse_error,
            KnowledgeDocument.is_active,
            KnowledgeDocument.synced_at,
            KnowledgeDocument.source_updated_at,
        ))
        .order_by(KnowledgeDocument.synced_at.desc(), KnowledgeDocument.id.desc())
    ).all()
    return [_document_output(document) for document in documents]


@router.get("/options", response_model=list[KnowledgeOptionOut])
def planner_options(
    current: Member = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[dict]:
    if not knowledge_enabled():
        return []
    rows = db.scalars(
        select(KnowledgeDocument)
        .options(load_only(
            KnowledgeDocument.id,
            KnowledgeDocument.source_type,
            KnowledgeDocument.source_name,
            KnowledgeDocument.title,
        ))
        .where(
            KnowledgeDocument.is_active.is_(True),
            KnowledgeDocument.parse_status.in_(("ready", "truncated")),
        )
        .order_by(KnowledgeDocument.title, KnowledgeDocument.id)
        .limit(200)
    ).all()
    return [
        {
            "id": row.id,
            "source_type": row.source_type,
            "source_name": row.source_name,
            "title": row.title,
        }
        for row in rows
    ]


@router.post("/sync/github", response_model=KnowledgeSyncOut)
def sync_github(
    current: Member = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, int]:
    if not knowledge_enabled():
        raise HTTPException(status_code=503, detail="团队知识功能尚未启用")
    repository = os.getenv("KNOWLEDGE_GITHUB_REPO", "").strip()
    branch = os.getenv("KNOWLEDGE_GITHUB_BRANCH", "main").strip() or "main"
    token = os.getenv("KNOWLEDGE_GITHUB_TOKEN", "").strip() or None
    if not repository:
        raise HTTPException(status_code=503, detail="尚未配置 GitHub 知识仓库")
    try:
        return sync_github_documents(
            db,
            repository=repository,
            branch=branch,
            token=token,
        )
    except KnowledgeConfigError:
        raise HTTPException(status_code=503, detail="GitHub 知识源配置无效") from None
    except KnowledgeSourceError:
        raise HTTPException(status_code=502, detail="GitHub 知识同步失败，请检查仓库和只读访问配置") from None
    except SQLAlchemyError as exc:
        db.rollback()
        logger.warning("knowledge github sync failed exception_type=%s", type(exc).__name__)
        raise HTTPException(status_code=500, detail="知识索引未能保存，请稍后重试") from None
    except Exception as exc:
        db.rollback()
        logger.warning("knowledge github sync failed exception_type=%s", type(exc).__name__)
        raise HTTPException(status_code=502, detail="GitHub 知识同步失败，请稍后重试") from None


@router.post("/uploads", response_model=KnowledgeDocumentOut, status_code=status.HTTP_201_CREATED)
def upload_document(
    file: UploadFile = File(...),
    current: Member = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    if not knowledge_enabled():
        raise HTTPException(status_code=503, detail="团队知识功能尚未启用")
    try:
        content = file.file.read(MAX_UPLOAD_BYTES + 1)
        if len(content) > MAX_UPLOAD_BYTES:
            raise UploadRejected(413, "单个文件不能超过 10MB")
        document = create_uploaded_document(
            db,
            created_by=current.id,
            filename=file.filename,
            data=content,
        )
        return _document_output(document)
    except UploadRejected as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from None
    except KnowledgeConfigError:
        db.rollback()
        logger.error("knowledge upload storage configuration is invalid")
        raise HTTPException(status_code=500, detail="服务器资料存储未配置") from None
    except Exception as exc:
        db.rollback()
        logger.warning("knowledge upload failed exception_type=%s", type(exc).__name__)
        raise HTTPException(status_code=500, detail="资料未能保存，请稍后重试") from None
    finally:
        file.file.close()


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_document(
    document_id: int,
    current: Member = Depends(require_admin),
    db: Session = Depends(get_db),
) -> None:
    document = db.scalar(
        select(KnowledgeDocument)
        .options(load_only(KnowledgeDocument.id, KnowledgeDocument.source_type, KnowledgeDocument.source_path))
        .where(KnowledgeDocument.id == document_id)
    )
    if document is None:
        raise HTTPException(status_code=404, detail="知识条目不存在")
    try:
        delete_document(db, document)
    except SQLAlchemyError as exc:
        db.rollback()
        logger.warning("knowledge document removal failed exception_type=%s", type(exc).__name__)
        raise HTTPException(status_code=500, detail="知识条目未能删除，请稍后重试") from None
    except Exception as exc:
        db.rollback()
        logger.warning("knowledge document removal failed exception_type=%s", type(exc).__name__)
        raise HTTPException(status_code=500, detail="知识条目未能删除，请稍后重试") from None
    logger.info("knowledge document removed document_id=%s actor_id=%s", document_id, current.id)
