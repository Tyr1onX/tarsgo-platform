"""link task progress to child tasks and add same-item dependencies

Revision ID: 0007_shared_execution_scene
Revises: 0006_dynamic_item_execution
Create Date: 2026-09-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0007_shared_execution_scene"
down_revision: Union[str, Sequence[str], None] = "0006_dynamic_item_execution"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("item_activities", sa.Column("task_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_item_activities_task_id_tasks",
        "item_activities",
        "tasks",
        ["task_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_item_activities_task_id", "item_activities", ["task_id"])
    op.create_table(
        "task_dependencies",
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("depends_on_task_id", sa.Integer(), nullable=False),
        sa.CheckConstraint("task_id <> depends_on_task_id", name="ck_task_dependencies_not_self"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["depends_on_task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("task_id", "depends_on_task_id"),
    )
    op.create_index(
        "ix_task_dependencies_depends_on",
        "task_dependencies",
        ["depends_on_task_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_task_dependencies_depends_on", table_name="task_dependencies")
    op.drop_table("task_dependencies")
    op.drop_index("ix_item_activities_task_id", table_name="item_activities")
    op.drop_constraint("fk_item_activities_task_id_tasks", "item_activities", type_="foreignkey")
    op.drop_column("item_activities", "task_id")
