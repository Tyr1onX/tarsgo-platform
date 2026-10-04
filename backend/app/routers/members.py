from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..auth import hash_token, new_token, require_admin, utcnow
from ..db import get_db
from ..models import Invitation, LoginSession, Member
from ..schemas import InviteCreate, InviteOut, MemberOut, MemberStudentIDUpdate

router = APIRouter(prefix="/api/members", tags=["members"])
INVITATION_TTL = timedelta(days=7)


def _create_invitation(db: Session, member: Member) -> InviteOut:
    db.execute(delete(Invitation).where(Invitation.member_id == member.id))
    token = new_token()
    expires_at = utcnow() + INVITATION_TTL
    db.add(Invitation(member_id=member.id, token_hash=hash_token(token), expires_at=expires_at))
    db.commit()
    db.refresh(member)
    return InviteOut(
        member=MemberOut.model_validate(member),
        invite_path=f"/invite/{token}",
        expires_at=expires_at,
    )


@router.get("", response_model=list[MemberOut])
def list_members(
    _: Member = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[Member]:
    return list(db.scalars(select(Member).order_by(Member.created_at.desc(), Member.id.desc())))


@router.post("/invite", response_model=InviteOut, status_code=status.HTTP_201_CREATED)
def invite_member(
    payload: InviteCreate,
    _: Member = Depends(require_admin),
    db: Session = Depends(get_db),
) -> InviteOut:
    if db.scalar(select(Member.id).where(Member.email == payload.email)) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该邮箱已存在")

    member = Member(name=payload.name, email=payload.email, role=payload.role, status="invited")
    db.add(member)
    db.flush()
    return _create_invitation(db, member)


@router.post("/{member_id}/invite", response_model=InviteOut)
def regenerate_invitation(
    member_id: int,
    _: Member = Depends(require_admin),
    db: Session = Depends(get_db),
) -> InviteOut:
    member = db.get(Member, member_id)
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="成员不存在")
    if member.status != "invited":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="只有待激活成员可以重新生成邀请")
    return _create_invitation(db, member)


@router.patch("/{member_id}/student-id", response_model=MemberOut)
def update_member_student_id(
    member_id: int,
    payload: MemberStudentIDUpdate,
    _: Member = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Member:
    member = db.get(Member, member_id)
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="成员不存在")
    member.student_id = payload.student_id
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该学号已被使用") from exc
    db.refresh(member)
    return member


@router.post("/{member_id}/disable", response_model=MemberOut)
def disable_member(
    member_id: int,
    current: Member = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Member:
    member = db.get(Member, member_id)
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="成员不存在")
    if member.id == current.id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="不能停用自己的账号")
    if member.status != "active":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="只有已激活成员可以停用")

    member.status = "disabled"
    db.execute(delete(Invitation).where(Invitation.member_id == member.id))
    db.execute(delete(LoginSession).where(LoginSession.member_id == member.id))
    db.commit()
    db.refresh(member)
    return member


@router.post("/{member_id}/enable", response_model=MemberOut)
def enable_member(
    member_id: int,
    _: Member = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Member:
    member = db.get(Member, member_id)
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="成员不存在")
    if member.status != "disabled" or not member.password_hash:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="只有已激活后停用的成员可以恢复",
        )

    member.status = "active"
    db.commit()
    db.refresh(member)
    return member
