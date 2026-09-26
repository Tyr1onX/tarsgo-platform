from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ..auth import hash_password, hash_token, utcnow
from ..db import get_db
from ..models import Invitation
from ..schemas import InvitationAccept, InvitationInfo

router = APIRouter(prefix="/api/invitations", tags=["invitations"])


def _get_invitation(db: Session, token: str) -> Invitation:
    invitation = db.scalar(
        select(Invitation)
        .options(joinedload(Invitation.member))
        .where(Invitation.token_hash == hash_token(token))
    )
    if not invitation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="邀请无效")
    if invitation.expires_at <= utcnow():
        db.delete(invitation)
        db.commit()
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="邀请已过期，请联系管理员重新生成")
    if invitation.member.status != "invited":
        db.delete(invitation)
        db.commit()
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="邀请已失效")
    return invitation


@router.get("/{token}", response_model=InvitationInfo)
def invitation_info(token: str, db: Session = Depends(get_db)) -> InvitationInfo:
    invitation = _get_invitation(db, token)
    return InvitationInfo(
        name=invitation.member.name,
        email=invitation.member.email,
        expires_at=invitation.expires_at,
    )


@router.post("/{token}/accept", status_code=status.HTTP_204_NO_CONTENT)
def accept_invitation(token: str, payload: InvitationAccept, db: Session = Depends(get_db)) -> None:
    invitation = _get_invitation(db, token)
    invitation.member.password_hash = hash_password(payload.password)
    invitation.member.status = "active"
    db.delete(invitation)
    db.commit()
