import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Cookie, Depends, HTTPException, Response, status
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from .db import get_db
from .models import LoginSession, Member

COOKIE_NAME = "tarsgo_session"
SESSION_TTL = timedelta(days=7)
_password_hash = PasswordHash.recommended()


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _password_hash.verify(password, password_hash)


def new_token() -> str:
    return secrets.token_urlsafe(32)


def create_login_session(db: Session, member: Member) -> str:
    token = new_token()
    db.add(
        LoginSession(
            member_id=member.id,
            token_hash=hash_token(token),
            expires_at=utcnow() + SESSION_TTL,
        )
    )
    db.commit()
    return token


def set_session_cookie(response: Response, token: str) -> None:
    secure = os.getenv("SESSION_COOKIE_SECURE", "false").lower() in {"1", "true", "yes"}
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=int(SESSION_TTL.total_seconds()),
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path="/")


def get_current_member(
    session_token: str | None = Cookie(default=None, alias=COOKIE_NAME),
    db: Session = Depends(get_db),
) -> Member:
    if not session_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请先登录")

    login_session = db.scalar(
        select(LoginSession)
        .options(joinedload(LoginSession.member))
        .where(LoginSession.token_hash == hash_token(session_token))
    )
    if not login_session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录已失效")

    if login_session.expires_at <= utcnow() or login_session.member.status != "active":
        db.delete(login_session)
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录已失效")

    return login_session.member


def require_admin(member: Member = Depends(get_current_member)) -> Member:
    if member.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问")
    return member
