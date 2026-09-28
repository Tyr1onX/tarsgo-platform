"""add dynamic item execution state

Revision ID: 0006_dynamic_item_execution
Revises: 0005_task_execution_details
Create Date: 2026-09-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision: str = "0006_dynamic_item_execution"
down_revision: Union[str, Sequence[str], None] = "0005_task_execution_details"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tasks",
        sa.Column("context_facts", mysql.JSON(), server_default=sa.text("(JSON_ARRAY())"), nullable=False),
    )
    op.add_column(
        "tasks",
        sa.Column("result", sa.Text(), nullable=True),
    )
    op.execute("UPDATE tasks SET result = '' WHERE result IS NULL")
    op.alter_column("tasks", "result", existing_type=sa.Text(), nullable=False)
    op.create_table(
        "item_activities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("root_task_id", sa.Integer(), nullable=False),
        sa.Column("author_id", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["root_task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["author_id"], ["members.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_item_activities_root_created",
        "item_activities",
        ["root_task_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_item_activities_root_created", table_name="item_activities")
    op.drop_table("item_activities")
    op.drop_column("tasks", "result")
    op.drop_column("tasks", "context_facts")
