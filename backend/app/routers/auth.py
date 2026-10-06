from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..auth import (
    COOKIE_NAME,
    clear_session_cookie,
    create_login_session,
    get_current_member,
    hash_token,
    set_session_cookie,
    verify_password,
)
from ..db import get_db
from ..models import LoginSession, Member
from ..schemas import LoginIn, MemberOut, MemberProfileUpdate

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=MemberOut)
def login(payload: LoginIn, response: Response, db: Session = Depends(get_db)) -> Member:
    member = db.scalar(select(Member).where(Member.email == payload.email))
    if not member or not member.password_hash or not verify_password(payload.password, member.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="邮箱或密码错误")
    if member.status == "disabled":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已停用")
    if member.status != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号尚未激活")

    token = create_login_session(db, member)
    set_session_cookie(response, token)
    return member


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    session_token: str | None = Cookie(default=None, alias=COOKIE_NAME),
    db: Session = Depends(get_db),
) -> None:
    if session_token:
        db.execute(delete(LoginSession).where(LoginSession.token_hash == hash_token(session_token)))
        db.commit()
    clear_session_cookie(response)


@router.get("/me", response_model=MemberOut)
def me(member: Member = Depends(get_current_member)) -> Member:
    return member


@router.patch("/me", response_model=MemberOut)
def update_me(
    payload: MemberProfileUpdate,
    member: Member = Depends(get_current_member),
    db: Session = Depends(get_db),
) -> Member:
    fields = payload.model_fields_set
    if "student_id" in fields:
        member.student_id = payload.student_id
    if "team_group" in fields:
        member.team_group = payload.team_group
    if "college" in fields:
        member.college = payload.college
    if "team_membership" in fields:
        member.team_membership = payload.team_membership
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该学号已被使用") from exc
    db.refresh(member)
    return member
