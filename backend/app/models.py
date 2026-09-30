from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Index,
    JSON,
    String,
    Table,
    Text,
    text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.mysql import LONGTEXT
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


task_dependencies = Table(
    "task_dependencies",
    Base.metadata,
    Column("task_id", ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True),
    Column("depends_on_task_id", ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True),
    CheckConstraint("task_id <> depends_on_task_id", name="ck_task_dependencies_not_self"),
    Index("ix_task_dependencies_depends_on", "depends_on_task_id"),
)


item_fact_tasks = Table(
    "item_fact_tasks",
    Base.metadata,
    Column("fact_id", ForeignKey("item_facts.id", ondelete="CASCADE"), primary_key=True),
    Column("task_id", ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True),
    Index("ix_item_fact_tasks_task_id", "task_id"),
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
        CheckConstraint(
            "owner_id IS NOT NULL OR owner_claimable = 1",
            name="ck_tasks_owner_or_claimable",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("tasks.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(200))
    deliverable: Mapped[str] = mapped_column(Text())
    execution_points: Mapped[list[str]] = mapped_column(
        JSON(), default=list, server_default=text("(JSON_ARRAY())"), nullable=False
    )
    cautions: Mapped[list[str]] = mapped_column(
        JSON(), default=list, server_default=text("(JSON_ARRAY())"), nullable=False
    )
    prerequisites: Mapped[list[str]] = mapped_column(
        JSON(), default=list, server_default=text("(JSON_ARRAY())"), nullable=False
    )
    result: Mapped[str] = mapped_column(Text(), default="", nullable=False)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("members.id"), nullable=True)
    owner_claimable: Mapped[bool] = mapped_column(Boolean(), default=False, server_default="0")
    collaboration_open: Mapped[bool] = mapped_column(Boolean(), default=False, server_default="0")
    deadline: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="todo")
    created_by: Mapped[int] = mapped_column(ForeignKey("members.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(), server_default=func.now())

    owner: Mapped[Member | None] = relationship(foreign_keys=[owner_id])
    creator: Mapped[Member] = relationship(foreign_keys=[created_by])
    collaborators: Mapped[list[Member]] = relationship(secondary=task_collaborators)
    depends_on_tasks: Mapped[list["Task"]] = relationship(
        "Task",
        secondary=task_dependencies,
        primaryjoin=lambda: Task.id == task_dependencies.c.task_id,
        secondaryjoin=lambda: Task.id == task_dependencies.c.depends_on_task_id,
        order_by=lambda: Task.id,
    )


class ItemActivity(Base):
    __tablename__ = "item_activities"
    __table_args__ = (
        Index("ix_item_activities_root_created", "root_task_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    root_task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    task_id: Mapped[int | None] = mapped_column(ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("members.id"), nullable=False)
    content: Mapped[str] = mapped_column(Text(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(), server_default=func.now(), nullable=False)

    root_task: Mapped[Task] = relationship(foreign_keys=[root_task_id])
    task: Mapped[Task | None] = relationship(foreign_keys=[task_id])
    author: Mapped[Member] = relationship(foreign_keys=[author_id])


class ItemFact(Base):
    __tablename__ = "item_facts"
    __table_args__ = (
        CheckConstraint("scope IN ('global','related')", name="ck_item_facts_scope"),
        Index("ix_item_facts_root_active", "root_task_id", "is_active", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    root_task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    content: Mapped[str] = mapped_column(Text(), nullable=False)
    scope: Mapped[str] = mapped_column(String(20), nullable=False)
    source_activity_id: Mapped[int | None] = mapped_column(
        ForeignKey("item_activities.id", ondelete="SET NULL"), nullable=True
    )
    created_by: Mapped[int] = mapped_column(ForeignKey("members.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(), server_default=func.now(), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean(), default=True, server_default="1", nullable=False)
    superseded_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("item_facts.id", ondelete="SET NULL"), nullable=True
    )
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)

    related_tasks: Mapped[list[Task]] = relationship(secondary=item_fact_tasks)
    source_activity: Mapped[ItemActivity | None] = relationship(foreign_keys=[source_activity_id])
    creator: Mapped[Member] = relationship(foreign_keys=[created_by])


class AIPlannerDailyUsage(Base):
    __tablename__ = "ai_planner_daily_usage"
    __table_args__ = (
        UniqueConstraint("member_id", "usage_date", name="uq_ai_planner_usage_member_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id", ondelete="CASCADE"))
    usage_date: Mapped[date] = mapped_column(Date())
    request_count: Mapped[int] = mapped_column(Integer(), default=0, server_default="0")
    input_tokens: Mapped[int] = mapped_column(BigInteger(), default=0, server_default="0")
    output_tokens: Mapped[int] = mapped_column(BigInteger(), default=0, server_default="0")
    total_tokens: Mapped[int] = mapped_column(BigInteger(), default=0, server_default="0")
    knowledge_context_chars: Mapped[int] = mapped_column(Integer(), default=0, server_default="0")
    updated_at: Mapped[datetime] = mapped_column(DateTime(), server_default=func.now(), onupdate=func.now())


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"
    __table_args__ = (
        CheckConstraint("source_type IN ('github','upload')", name="ck_knowledge_source_type"),
        CheckConstraint(
            "parse_status IN ('ready','truncated','failed','unparseable','removed')",
            name="ck_knowledge_parse_status",
        ),
        UniqueConstraint("source_key_hash", name="uq_knowledge_source_key_hash"),
        Index("ix_knowledge_source_active_status", "source_type", "source_name", "is_active", "parse_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    source_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content_text: Mapped[str] = mapped_column(Text().with_variant(LONGTEXT(), "mysql"), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source_blob_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    git_commit_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    synced_at: Mapped[datetime] = mapped_column(DateTime(), server_default=func.now(), nullable=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("members.id", ondelete="SET NULL"), nullable=True)
    parse_status: Mapped[str] = mapped_column(String(20), nullable=False)
    parse_error: Mapped[str | None] = mapped_column(String(200), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean(), default=True, server_default="1", nullable=False)
