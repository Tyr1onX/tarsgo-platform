"""add operations claiming and one-level task hierarchy

Revision ID: 0002_operations_claiming
Revises: 0001_v0_1
Create Date: 2026-09-26
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002_operations_claiming"
down_revision: Union[str, Sequence[str], None] = "0001_v0_1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("parent_id", sa.Integer(), nullable=True))
    op.add_column(
        "tasks",
        sa.Column("owner_claimable", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column(
        "tasks",
        sa.Column("collaboration_open", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.alter_column("tasks", "owner_id", existing_type=sa.Integer(), nullable=True)
    op.create_foreign_key(
        "fk_tasks_parent_id_tasks",
        "tasks",
        "tasks",
        ["parent_id"],
        ["id"],
    )
    op.create_check_constraint(
        "ck_tasks_owner_or_claimable",
        "tasks",
        "owner_id IS NOT NULL OR owner_claimable = 1",
    )


def downgrade() -> None:
    op.drop_constraint("ck_tasks_owner_or_claimable", "tasks", type_="check")
    op.drop_constraint("fk_tasks_parent_id_tasks", "tasks", type_="foreignkey")
    op.execute("UPDATE tasks SET owner_id = created_by WHERE owner_id IS NULL")
    op.alter_column("tasks", "owner_id", existing_type=sa.Integer(), nullable=False)
    op.drop_column("tasks", "collaboration_open")
    op.drop_column("tasks", "owner_claimable")
    op.drop_column("tasks", "parent_id")
