from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..auth import get_current_member, new_token, require_admin
from ..college_dictionary import COLLEGE_BY_CODE
from ..db import get_db
from ..models import CampLeaveEvent, CampLeaveParticipant, Member
from ..schemas import (
    CampLeaveAdminEventDetailOut,
    CampLeaveAdminEventOut,
    CampLeaveEventCreate,
    CampLeaveEventMemberOut,
    CampLeaveParticipantGroupOut,
    CampLeaveParticipantOut,
    CampLeavePublicEventOut,
    CampLeavePublicParticipantCreate,
    CampLeavePublicSubmissionOut,
    validate_college,
    validate_member_name,
    validate_student_id,
)


router = APIRouter(prefix="/api/camp-leave", tags=["camp-leave"])
SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")


def camp_leave_now() -> datetime:
    return datetime.now(SHANGHAI_TZ).replace(tzinfo=None, second=0, microsecond=0)


def event_accepting(event: CampLeaveEvent, *, now: datetime | None = None) -> bool:
    return event.status == "collecting" and event.collection_deadline > (now or camp_leave_now())


def get_event(db: Session, event_id: int, *, lock: bool = False) -> CampLeaveEvent:
    query = select(CampLeaveEvent).where(CampLeaveEvent.id == event_id)
    if lock:
        query = query.with_for_update()
    event = db.scalar(query)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="集中请假活动不存在")
    return event


def require_open_event(event: CampLeaveEvent) -> None:
    if not event_accepting(event):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="本次活动已停止收集报名")


def member_event_out(event: CampLeaveEvent, current: Member, participant: CampLeaveParticipant | None):
    return CampLeaveEventMemberOut(
        id=event.id,
        title=event.title,
        type=event.type,
        start_date=event.start_date,
        end_date=event.end_date,
        collection_deadline=event.collection_deadline,
        status=event.status,
        accepting_participants=event_accepting(event),
        joined=participant is not None,
        participant_type=participant.participant_type if participant else None,
        submitted_at=participant.submitted_at if participant else None,
    )


def admin_event_out(event: CampLeaveEvent, participant_count: int) -> CampLeaveAdminEventOut:
    return CampLeaveAdminEventOut(
        id=event.id,
        title=event.title,
        type=event.type,
        start_date=event.start_date,
        end_date=event.end_date,
        collection_deadline=event.collection_deadline,
        status=event.status,
        accepting_participants=event_accepting(event),
        participant_count=participant_count,
        public_path=f"/leave/camp/{event.public_token}",
        created_at=event.created_at,
    )


def grouped_participants(participants: list[CampLeaveParticipant]) -> list[CampLeaveParticipantGroupOut]:
    groups: dict[str, list[CampLeaveParticipant]] = defaultdict(list)
    for participant in participants:
        groups[participant.college_snapshot].append(participant)

    outputs: list[CampLeaveParticipantGroupOut] = []
    for code in COLLEGE_BY_CODE:
        rows = groups.get(code, [])
        if not rows:
            continue
        option = COLLEGE_BY_CODE[code]
        outputs.append(
            CampLeaveParticipantGroupOut(
                college=code,
                college_name=option["name"],
                count=len(rows),
                participants=[
                    CampLeaveParticipantOut(
                        id=row.id,
                        name=row.name_snapshot,
                        student_id=row.student_id_snapshot,
                        college=row.college_snapshot,
                        college_name=option["name"],
                        participant_type=row.participant_type,
                        submitted_at=row.submitted_at,
                    )
                    for row in sorted(rows, key=lambda item: (item.name_snapshot, item.student_id_snapshot))
                ],
            )
        )
    return outputs


def _public_event(token: str, db: Session) -> CampLeaveEvent:
    # New tokens contain 256 random bits and use the URL-safe alphabet. Reject
    # malformed values before querying, and keep every response token-free.
    if not 40 <= len(token) <= 50 or any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for char in token):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="报名链接无效")
    event = db.scalar(select(CampLeaveEvent).where(CampLeaveEvent.public_token == token))
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="报名链接无效")
    return event


@router.get("/events", response_model=list[CampLeaveEventMemberOut])
def member_events(
    current: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
) -> list[CampLeaveEventMemberOut]:
    events = list(db.scalars(select(CampLeaveEvent).order_by(CampLeaveEvent.start_date.desc(), CampLeaveEvent.id.desc())))
    participants = {
        row.event_id: row
        for row in db.scalars(
            select(CampLeaveParticipant).where(CampLeaveParticipant.member_id == current.id)
        )
    }
    # Members see events accepting participants and historical events they joined.
    # The response never includes counts, other participants, or public tokens.
    return [
        member_event_out(event, current, participants.get(event.id))
        for event in events
        if event_accepting(event) or participants.get(event.id) is not None
    ]


@router.post("/events/{event_id}/join", response_model=CampLeaveEventMemberOut, status_code=status.HTTP_201_CREATED)
def join_event(
    event_id: int,
    current: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
) -> CampLeaveEventMemberOut:
    event = get_event(db, event_id, lock=True)
    require_open_event(event)
    if current.team_membership not in {"formal", "reserve"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请先完善个人资料中的队内身份")
    try:
        name = validate_member_name(current.name or "")
        student_id = validate_student_id(current.student_id or "")
        college = validate_college(current.college or "")
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请先完善个人资料中的姓名、学号和学院",
        ) from exc

    existing = db.scalar(
        select(CampLeaveParticipant).where(
            CampLeaveParticipant.event_id == event.id,
            or_(
                CampLeaveParticipant.member_id == current.id,
                CampLeaveParticipant.student_id_snapshot == student_id,
            ),
        )
    )
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="你已参加本次活动，或该学号已报名")

    participant = CampLeaveParticipant(
        event_id=event.id,
        member_id=current.id,
        name_snapshot=name,
        student_id_snapshot=student_id,
        college_snapshot=college,
        participant_type=current.team_membership,
    )
    db.add(participant)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该学号已在本活动报名") from exc
    db.refresh(participant)
    return member_event_out(event, current, participant)


@router.post("/events/{event_id}/leave", response_model=CampLeaveEventMemberOut)
def leave_event(
    event_id: int,
    current: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
) -> CampLeaveEventMemberOut:
    event = get_event(db, event_id, lock=True)
    require_open_event(event)
    participant = db.scalar(
        select(CampLeaveParticipant)
        .where(CampLeaveParticipant.event_id == event.id, CampLeaveParticipant.member_id == current.id)
        .with_for_update()
    )
    if participant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到你的报名记录")
    db.delete(participant)
    db.commit()
    return member_event_out(event, current, None)


@router.get("/admin/events", response_model=list[CampLeaveAdminEventOut])
def admin_events(
    _: Member = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[CampLeaveAdminEventOut]:
    events = list(db.scalars(select(CampLeaveEvent).order_by(CampLeaveEvent.start_date.desc(), CampLeaveEvent.id.desc())))
    counts = dict(
        db.execute(
            select(CampLeaveParticipant.event_id, func.count(CampLeaveParticipant.id))
            .group_by(CampLeaveParticipant.event_id)
        ).all()
    )
    return [admin_event_out(event, counts.get(event.id, 0)) for event in events]


@router.post("/admin/events", response_model=CampLeaveAdminEventOut, status_code=status.HTTP_201_CREATED)
def create_event(
    payload: CampLeaveEventCreate,
    current: Member = Depends(require_admin),
    db: Session = Depends(get_db),
) -> CampLeaveAdminEventOut:
    event = CampLeaveEvent(
        title=payload.title,
        type=payload.type,
        start_date=payload.start_date,
        end_date=payload.end_date,
        collection_deadline=payload.collection_deadline,
        status="collecting",
        public_token=new_token(),
        created_by=current.id,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return admin_event_out(event, 0)


@router.get("/admin/events/{event_id}", response_model=CampLeaveAdminEventDetailOut)
def admin_event_detail(
    event_id: int,
    _: Member = Depends(require_admin),
    db: Session = Depends(get_db),
) -> CampLeaveAdminEventDetailOut:
    event = get_event(db, event_id)
    participants = list(
        db.scalars(
            select(CampLeaveParticipant)
            .where(CampLeaveParticipant.event_id == event.id)
            .order_by(CampLeaveParticipant.college_snapshot, CampLeaveParticipant.name_snapshot)
        )
    )
    return CampLeaveAdminEventDetailOut(
        event=admin_event_out(event, len(participants)),
        groups=grouped_participants(participants),
    )


@router.post("/admin/events/{event_id}/close", response_model=CampLeaveAdminEventOut)
def close_event(
    event_id: int,
    _: Member = Depends(require_admin),
    db: Session = Depends(get_db),
) -> CampLeaveAdminEventOut:
    event = get_event(db, event_id, lock=True)
    if event.status != "closed":
        event.status = "closed"
        db.commit()
        db.refresh(event)
    count = db.scalar(
        select(func.count(CampLeaveParticipant.id)).where(CampLeaveParticipant.event_id == event.id)
    ) or 0
    return admin_event_out(event, count)


@router.delete("/admin/events/{event_id}/participants/{participant_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_participant(
    event_id: int,
    participant_id: int,
    _: Member = Depends(require_admin),
    db: Session = Depends(get_db),
) -> None:
    event = get_event(db, event_id, lock=True)
    require_open_event(event)
    participant = db.scalar(
        select(CampLeaveParticipant)
        .where(CampLeaveParticipant.id == participant_id, CampLeaveParticipant.event_id == event.id)
        .with_for_update()
    )
    if participant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="报名记录不存在")
    db.delete(participant)
    db.commit()


@router.get("/public/{token}", response_model=CampLeavePublicEventOut)
def public_event(token: str, db: Session = Depends(get_db)) -> CampLeavePublicEventOut:
    event = _public_event(token, db)
    return CampLeavePublicEventOut(
        title=event.title,
        type=event.type,
        start_date=event.start_date,
        end_date=event.end_date,
        collection_deadline=event.collection_deadline,
        status=event.status,
        accepting_participants=event_accepting(event),
    )


@router.post(
    "/public/{token}/participants",
    response_model=CampLeavePublicSubmissionOut,
    status_code=status.HTTP_201_CREATED,
)
def public_join_event(
    token: str,
    payload: CampLeavePublicParticipantCreate,
    db: Session = Depends(get_db),
) -> CampLeavePublicSubmissionOut:
    event = _public_event(token, db)
    # Lock the event row so close/submit and concurrent submissions serialize.
    event = get_event(db, event.id, lock=True)
    require_open_event(event)
    db.add(
        CampLeaveParticipant(
            event_id=event.id,
            member_id=None,
            name_snapshot=payload.name,
            student_id_snapshot=payload.student_id,
            college_snapshot=payload.college,
            participant_type="other",
        )
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该学号已在本活动报名") from exc
    return CampLeavePublicSubmissionOut()
