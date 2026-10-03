import logging
import os
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from ..ai_planner import (
    PlannerInvalidResponse,
    PlannerProvider,
    PlannerProviderError,
    PlannerRateLimitError,
    PlannerTimeoutError,
    get_planner_provider,
    provider_is_configured,
)
from ..auth import get_current_member
from ..db import get_db
from ..knowledge import (
    MAX_UPLOAD_BYTES,
    KnowledgeContext,
    UploadRejected,
    _safe_upload_name,
    build_planner_context,
    extract_document_text,
    planner_input_text,
)
from ..models import AIPlannerDailyUsage, Member
from ..schemas import (
    AIPlannerAccessOut,
    AIPlannerDraft,
    AIPlannerExtractOut,
    AIPlannerGenerateOut,
    AIPlannerRefineRequest,
    AIPlannerRequest,
    KnowledgeReferenceOut,
)

router = APIRouter(prefix="/api/ai/planner", tags=["ai-planner"])
logger = logging.getLogger(__name__)
DAILY_REQUEST_LIMIT = int(os.getenv("AI_PLANNER_DAILY_REQUEST_LIMIT", "100"))
DAILY_REQUEST_LIMIT_MESSAGE = "今日 AI 使用次数已达上限，请稍后再试。"
_LIVESTREAM_NEGATION = re.compile(
    r"(?:不需要|不必|不要|无需|不用|不做|不安排|不考虑|不打算|不进行|取消)"
    r"[^。；;，,\n]{0,8}(?:现场直播|线上直播|直播|线上转播)"
    r"|(?:现场直播|线上直播|直播|线上转播)[^。；;，,\n]{0,8}"
    r"(?:不需要|不必|不要|无需|不用|不做|不安排|不考虑|不打算|取消)"
)
_EXPLICIT_NETWORK_NEED = re.compile(r"联网展示|在线演示|网络演示|网络展示|网络条件[^。；;，,\n]{0,4}(?:未知|不确定|待确认|需确认)")


def _enabled() -> bool:
    return os.getenv("AI_PLANNER_ENABLED", "false").strip().lower() in {"1", "true", "yes"}


def _server_configured() -> bool:
    return provider_is_configured()


def _has_access(member: Member) -> bool:
    return member.status == "active" and member.role == "admin" and _enabled() and _server_configured()


def _remove_blocked_fragments(value: str, blocked_terms: re.Pattern[str]) -> str:
    fragments = re.split(r"([，,；;。！？\n])", value)
    kept: list[str] = []
    for index in range(0, len(fragments), 2):
        fragment = fragments[index]
        separator = fragments[index + 1] if index + 1 < len(fragments) else ""
        if blocked_terms.search(fragment):
            continue
        kept.extend((fragment, separator))
    return re.sub(r"^[，,；;\s]+|[，,；;\s]+$", "", "".join(kept)).strip()


def _apply_explicit_topic_veto(draft: AIPlannerDraft, current_facts: str) -> None:
    """Apply explicit user exclusions to all planner output layers after generation."""
    if not _LIVESTREAM_NEGATION.search(current_facts):
        return
    blocked_terms = [r"直播", r"线上转播"]
    if not _EXPLICIT_NETWORK_NEED.search(current_facts):
        blocked_terms.extend((r"网络", r"联网", r"在线演示"))
    blocked = re.compile("|".join(blocked_terms))
    draft.item.deliverable = _remove_blocked_fragments(draft.item.deliverable, blocked)

    filtered_tasks = []
    for task in draft.tasks:
        if blocked.search(task.title):
            continue
        original_deliverable = task.deliverable
        task.deliverable = _remove_blocked_fragments(task.deliverable, blocked)
        if original_deliverable and not task.deliverable:
            continue
        for field in ("execution_points", "cautions", "prerequisites"):
            setattr(
                task,
                field,
                [
                    cleaned
                    for entry in getattr(task, field)
                    if (cleaned := _remove_blocked_fragments(entry, blocked))
                ],
            )
        filtered_tasks.append(task)
    if not filtered_tasks:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="规划结果与已明确排除的事项冲突，请重新生成")
    draft.tasks = filtered_tasks
    draft.questions = [
        cleaned
        for question in draft.questions
        if (cleaned := _remove_blocked_fragments(question, blocked))
    ]
    draft.suggestions = [
        suggestion
        for suggestion in draft.suggestions
        if not blocked.search(suggestion.title)
        and not blocked.search(suggestion.reason)
    ]


def _require_planner_access(member: Member) -> None:
    if member.status != "active" or member.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权使用 AI 规划")
    if not _enabled():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="AI 规划当前未启用")
    if not _server_configured():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="AI 规划尚未完成服务器配置")


def _usage_date():
    return datetime.now(timezone.utc).date()


def _reserve_request(db: Session, member_id: int, knowledge_context_chars: int = 0):
    usage_date = _usage_date()
    for attempt in range(2):
        try:
            usage = db.scalar(
                select(AIPlannerDailyUsage)
                .where(AIPlannerDailyUsage.member_id == member_id, AIPlannerDailyUsage.usage_date == usage_date)
                .with_for_update()
            )
            if usage is None:
                db.add(
                    AIPlannerDailyUsage(
                        member_id=member_id,
                        usage_date=usage_date,
                        request_count=1,
                        knowledge_context_chars=max(knowledge_context_chars, 0),
                    )
                )
            else:
                if usage.request_count >= DAILY_REQUEST_LIMIT:
                    db.rollback()
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail=DAILY_REQUEST_LIMIT_MESSAGE,
                    )
                usage.request_count += 1
                usage.knowledge_context_chars += max(knowledge_context_chars, 0)
            db.commit()
            return usage_date
        except IntegrityError:
            db.rollback()
            if attempt == 1:
                raise
    raise RuntimeError("unreachable")


def _record_tokens(db: Session, member_id: int, usage_date, input_tokens: int, output_tokens: int, total_tokens: int) -> None:
    usage = db.scalar(
        select(AIPlannerDailyUsage)
        .where(AIPlannerDailyUsage.member_id == member_id, AIPlannerDailyUsage.usage_date == usage_date)
        .with_for_update()
    )
    if usage is None:
        return
    usage.input_tokens += max(input_tokens, 0)
    usage.output_tokens += max(output_tokens, 0)
    usage.total_tokens += max(total_tokens, 0)
    db.commit()


def _build_context(db: Session, payload: AIPlannerRequest) -> KnowledgeContext:
    try:
        return build_planner_context(
            db,
            description=payload.description,
            item_title=payload.item_title,
            current_event_context=payload.current_event_context,
            current_event_document_ids=payload.current_event_document_ids,
            excluded_historical_document_ids=payload.excluded_historical_document_ids,
        )
    except Exception as exc:
        db.rollback()
        logger.warning("AI planner knowledge context unavailable exception_type=%s", type(exc).__name__)
        pasted = (payload.current_event_context or "").strip()
        header = "负责人补充资料：\n"
        fallback = header + pasted[: max(0, 5_000 - len(header))] if pasted else ""
        return KnowledgeContext(current_event_text=fallback)


def _generate_once(provider: PlannerProvider, planner_input: str):
    try:
        return provider.generate(planner_input)
    except PlannerTimeoutError:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="AI 规划请求超时，请稍后重试")
    except PlannerRateLimitError:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="AI 服务暂时繁忙，请稍后重试")
    except PlannerInvalidResponse:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="这次规划没有生成成功，请稍后重试")
    except PlannerProviderError:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="AI 服务暂时不可用，请稍后重试")


def _record_generation_tokens(db: Session, member_id: int, usage_date, generation) -> None:
    try:
        _record_tokens(db, member_id, usage_date, generation.input_tokens, generation.output_tokens, generation.total_tokens)
    except SQLAlchemyError:
        db.rollback()
        logger.warning("AI planner token accounting failed member_id=%s", member_id)


def _generation_out(generation, context: KnowledgeContext) -> AIPlannerGenerateOut:
    return AIPlannerGenerateOut(
        draft=generation.draft,
        current_event_documents=[
            KnowledgeReferenceOut.model_validate(reference.__dict__)
            for reference in context.current_event_documents
        ],
        historical_documents=[
            KnowledgeReferenceOut.model_validate(reference.__dict__)
            for reference in context.historical_documents
        ],
    )


@router.get("/access", response_model=AIPlannerAccessOut)
def planner_access(current: Member = Depends(get_current_member)) -> AIPlannerAccessOut:
    return AIPlannerAccessOut(available=_has_access(current))


@router.post("/extract", response_model=AIPlannerExtractOut)
def extract_planner_material(
    file: UploadFile = File(...),
    current: Member = Depends(get_current_member),
) -> AIPlannerExtractOut:
    try:
        _require_planner_access(current)
        content = file.file.read(MAX_UPLOAD_BYTES + 1)
        if len(content) > MAX_UPLOAD_BYTES:
            raise UploadRejected(413, "单个文件不能超过 10 MiB")
        filename = _safe_upload_name(file.filename)
        extracted = extract_document_text(filename, content)
        return AIPlannerExtractOut(
            filename=filename,
            extracted_text=extracted.content_text,
            parse_status=extracted.parse_status,
            error=extracted.parse_error,
        )
    except UploadRejected as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from None
    finally:
        file.file.close()


@router.post("", response_model=AIPlannerGenerateOut)
def generate_plan(
    payload: AIPlannerRequest,
    current: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
    provider: PlannerProvider = Depends(get_planner_provider),
) -> AIPlannerGenerateOut:
    _require_planner_access(current)
    context = _build_context(db, payload)
    planner_input = planner_input_text(payload.description, payload.item_title, context)
    usage_date = _reserve_request(db, current.id, context.context_chars)
    generation = _generate_once(provider, planner_input)
    generation.draft.item.deliverable = ""
    _apply_explicit_topic_veto(
        generation.draft,
        "\n".join((payload.description, payload.current_event_context or "")),
    )
    _record_generation_tokens(db, current.id, usage_date, generation)
    return _generation_out(generation, context)


@router.post("/refine", response_model=AIPlannerGenerateOut)
def refine_plan(
    payload: AIPlannerRefineRequest,
    current: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
    provider: PlannerProvider = Depends(get_planner_provider),
) -> AIPlannerGenerateOut:
    _require_planner_access(current)
    context = _build_context(db, payload)
    planner_input = planner_input_text(payload.description, payload.item_title, context)
    current_task_numbering = "\n".join(
        f"{index}. {task.title}"
        for index, task in enumerate(payload.draft.tasks, start=1)
    ) or "（当前草案没有执行任务）"
    scope_index = payload.scope_task_index
    scope_note = (
        f"本次只调整第 {scope_index + 1} 张任务卡。请在返回 draft.tasks 中只输出这一张调整后的任务卡；"
        "不要修改事项字段、确认问题或其他卡片。"
        if scope_index is not None
        else "本次是全局调整。请根据指令修改完整草案，并保留未要求改变且仍合理的部分。"
    )
    planner_input += (
        "\n\n【当前 AI 草案 JSON】\n"
        + payload.draft.model_dump_json(indent=2)
        + "\n\n【当前任务编号】\n"
        + current_task_numbering
        + "\n编号从 1 开始，对应当前 draft.tasks 顺序；“第 N 个 / 第 N 项 / 第 N 张任务 / 任务 N”均指此处编号。"
        + "编号不是数据库 ID，不写入输出字段；每次 refine 都必须按收到的最新 draft 重新编号。"
        + "\n\n【调整范围】\n"
        + scope_note
        + "\n\n【用户调整指令】\n"
        + payload.instruction
    )
    usage_date = _reserve_request(db, current.id, context.context_chars)
    generation = _generate_once(provider, planner_input)

    if scope_index is not None:
        updated = generation.draft.tasks[0]
        original = payload.draft.tasks[scope_index]
        merged = payload.draft.model_copy(deep=True)
        merged.tasks[scope_index] = updated.model_copy(
            update={
                "owner_claimable": original.owner_claimable,
                "collaboration_open": original.collaboration_open,
            }
        )
        generation.draft = merged
    else:
        generation.draft.item.deliverable = ""

    _apply_explicit_topic_veto(
        generation.draft,
        "\n".join((payload.description, payload.current_event_context or "", payload.instruction)),
    )

    _record_generation_tokens(db, current.id, usage_date, generation)
    return _generation_out(generation, context)
