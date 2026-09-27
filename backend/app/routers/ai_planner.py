import logging
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
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
)
from ..auth import get_current_member
from ..db import get_db
from ..models import AIPlannerDailyUsage, Member
from ..schemas import AIPlannerAccessOut, AIPlannerDraft, AIPlannerRequest

router = APIRouter(prefix="/api/ai/planner", tags=["ai-planner"])
logger = logging.getLogger(__name__)
DAILY_REQUEST_LIMIT = 20


def _enabled() -> bool:
    return os.getenv("AI_PLANNER_ENABLED", "false").strip().lower() in {"1", "true", "yes"}


def _allowed_member_ids() -> set[int]:
    result: set[int] = set()
    for part in os.getenv("AI_PLANNER_ALLOWED_MEMBER_IDS", "").split(","):
        value = part.strip()
        if not value:
            continue
        try:
            result.add(int(value))
        except ValueError:
            continue
    return result


def _server_configured() -> bool:
    return bool(os.getenv("AI_API_KEY", "").strip() and os.getenv("AI_MODEL", "").strip())


def _has_access(member: Member) -> bool:
    return member.role == "admin" and member.id in _allowed_member_ids() and _enabled() and _server_configured()


def _require_planner_access(member: Member) -> None:
    if member.role != "admin" or member.id not in _allowed_member_ids():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权使用 AI 规划")
    if not _enabled():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="AI 规划当前未启用")
    if not _server_configured():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="AI 规划尚未完成服务器配置")


def _usage_date():
    return datetime.now(timezone.utc).date()


def _reserve_request(db: Session, member_id: int):
    usage_date = _usage_date()
    for attempt in range(2):
        try:
            usage = db.scalar(
                select(AIPlannerDailyUsage)
                .where(AIPlannerDailyUsage.member_id == member_id, AIPlannerDailyUsage.usage_date == usage_date)
                .with_for_update()
            )
            if usage is None:
                db.add(AIPlannerDailyUsage(member_id=member_id, usage_date=usage_date, request_count=1))
            else:
                if usage.request_count >= DAILY_REQUEST_LIMIT:
                    db.rollback()
                    raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="今天的 AI 规划次数已用完，请明天再试")
                usage.request_count += 1
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


@router.get("/access", response_model=AIPlannerAccessOut)
def planner_access(current: Member = Depends(get_current_member)) -> AIPlannerAccessOut:
    return AIPlannerAccessOut(available=_has_access(current))


@router.post("", response_model=AIPlannerDraft)
def generate_plan(
    payload: AIPlannerRequest,
    current: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
    provider: PlannerProvider = Depends(get_planner_provider),
) -> AIPlannerDraft:
    _require_planner_access(current)
    usage_date = _reserve_request(db, current.id)

    try:
        generation = provider.generate(payload.description)
    except PlannerTimeoutError:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="AI 规划请求超时，请稍后重试")
    except PlannerRateLimitError:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="AI 服务暂时繁忙，请稍后重试")
    except PlannerInvalidResponse:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="这次规划没有生成成功，请稍后重试")
    except PlannerProviderError:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="AI 服务暂时不可用，请稍后重试")

    try:
        _record_tokens(db, current.id, usage_date, generation.input_tokens, generation.output_tokens, generation.total_tokens)
    except SQLAlchemyError:
        db.rollback()
        logger.warning("AI planner token accounting failed member_id=%s", current.id)

    return generation.draft
