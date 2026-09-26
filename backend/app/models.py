from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Table, Text, Column, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


ROLE_VALUES = ("admin", "manager", "member")
MEMBER_STATUS_VALUES = ("invited", "active", "disabled")
TASK_STATUS_VALUES = ("todo", "doing", "done")


task_collaborators = Table(
    "task_collaborators",
    Base.metadata,
    Column("task_id", ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True),
    Column("member_id", ForeignKey("members.id", ondelete="CASCADE"), primary_key=True),
)


class Member(Base):
    __tablename__ = "members"
    __table_args__ = (
        CheckConstraint("role IN ('admin','manager','member')", name="ck_members_role"),
        CheckConstraint("status IN ('invited','active','disabled')", name="ck_members_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(String(20), default="member")
    status: Mapped[str] = mapped_column(String(20), default="invited")
    created_at: Mapped[datetime] = mapped_column(DateTime(), server_default=func.now())


class Invitation(Base):
    __tablename__ = "invitations"

    id: Mapped[int] = mapped_column(primary_key=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id", ondelete="CASCADE"), unique=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime())
    created_at: Mapped[datetime] = mapped_column(DateTime(), server_default=func.now())

    member: Mapped[Member] = relationship()


class LoginSession(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime())
    created_at: Mapped[datetime] = mapped_column(DateTime(), server_default=func.now())

    member: Mapped[Member] = relationship()


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint("status IN ('todo','doing','done')", name="ck_tasks_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    deliverable: Mapped[str] = mapped_column(Text())
    owner_id: Mapped[int] = mapped_column(ForeignKey("members.id"))
    deadline: Mapped[datetime] = mapped_column(DateTime())
    status: Mapped[str] = mapped_column(String(20), default="todo")
    created_by: Mapped[int] = mapped_column(ForeignKey("members.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(), server_default=func.now())

    owner: Mapped[Member] = relationship(foreign_keys=[owner_id])
    creator: Mapped[Member] = relationship(foreign_keys=[created_by])
    collaborators: Mapped[list[Member]] = relationship(secondary=task_collaborators)
