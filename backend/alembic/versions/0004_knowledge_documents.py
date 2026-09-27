"""add knowledge documents and planner knowledge usage

Revision ID: 0004_knowledge_documents
Revises: 0003_ai_planner_usage
Create Date: 2026-09-27
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision: str = "0004_knowledge_documents"
down_revision: Union[str, Sequence[str], None] = "0003_ai_planner_usage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ai_planner_daily_usage",
        sa.Column("knowledge_context_chars", sa.Integer(), server_default="0", nullable=False),
    )
    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_type", sa.String(length=20), nullable=False),
        sa.Column("source_name", sa.String(length=255), nullable=False),
        sa.Column("source_path", sa.String(length=1024), nullable=False),
        sa.Column("source_key_hash", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content_text", mysql.LONGTEXT(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("source_blob_sha", sa.String(length=64), nullable=True),
        sa.Column("git_commit_sha", sa.String(length=64), nullable=True),
        sa.Column("source_updated_at", sa.DateTime(), nullable=True),
        sa.Column("synced_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("parse_status", sa.String(length=20), nullable=False),
        sa.Column("parse_error", sa.String(length=200), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.CheckConstraint("source_type IN ('github','upload')", name="ck_knowledge_source_type"),
        sa.CheckConstraint(
            "parse_status IN ('ready','truncated','failed','unparseable','removed')",
            name="ck_knowledge_parse_status",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["members.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("source_key_hash", name="uq_knowledge_source_key_hash"),
    )
    op.create_index(
        "ix_knowledge_source_active_status",
        "knowledge_documents",
        ["source_type", "source_name", "is_active", "parse_status"],
    )


def downgrade() -> None:
    op.drop_index("ix_knowledge_source_active_status", table_name="knowledge_documents")
    op.drop_table("knowledge_documents")
    op.drop_column("ai_planner_daily_usage", "knowledge_context_chars")
