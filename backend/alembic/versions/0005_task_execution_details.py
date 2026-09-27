"""add concise execution details to tasks

Revision ID: 0005_task_execution_details
Revises: 0004_knowledge_documents
Create Date: 2026-09-27
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision: str = "0005_task_execution_details"
down_revision: Union[str, Sequence[str], None] = "0004_knowledge_documents"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for name in ("execution_points", "cautions", "prerequisites"):
        op.add_column(
            "tasks",
            sa.Column(name, mysql.JSON(), server_default=sa.text("(JSON_ARRAY())"), nullable=False),
        )


def downgrade() -> None:
    for name in ("prerequisites", "cautions", "execution_points"):
        op.drop_column("tasks", name)
