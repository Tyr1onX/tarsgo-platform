"""make task deadlines optional

Revision ID: 0009_optional_task_deadlines
Revises: 0008_scoped_item_information
Create Date: 2026-09-30
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0009_optional_task_deadlines"
down_revision: Union[str, Sequence[str], None] = "0008_scoped_item_information"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("tasks", "deadline", existing_type=sa.DateTime(), nullable=True)


def downgrade() -> None:
    bind = op.get_bind()
    tasks = sa.table("tasks", sa.column("deadline", sa.DateTime()))
    null_count = bind.scalar(sa.select(sa.func.count()).select_from(tasks).where(tasks.c.deadline.is_(None)))
    if null_count:
        raise RuntimeError("Cannot require task deadlines while rows without deadlines exist")
    op.alter_column("tasks", "deadline", existing_type=sa.DateTime(), nullable=False)
