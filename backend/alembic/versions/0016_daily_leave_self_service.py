"""allow standalone daily leave generations

Revision ID: 0016_daily_leave_self_service
Revises: 0015_leave_v2_windows
Create Date: 2026-10-06
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0016_daily_leave_self_service"
down_revision: Union[str, Sequence[str], None] = "0015_leave_v2_windows"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "daily_leave_entries",
        "window_id",
        existing_type=sa.Integer(),
        existing_nullable=False,
        nullable=True,
    )
    op.add_column("daily_leave_entries", sa.Column("start_at", sa.DateTime(), nullable=True))
    op.add_column("daily_leave_entries", sa.Column("end_at", sa.DateTime(), nullable=True))
    op.create_check_constraint(
        "ck_daily_leave_entries_source_time_shape",
        "daily_leave_entries",
        "(window_id IS NOT NULL AND start_at IS NULL AND end_at IS NULL) OR "
        "(window_id IS NULL AND start_at IS NOT NULL AND end_at IS NOT NULL AND start_at < end_at)",
    )


def downgrade() -> None:
    connection = op.get_bind()
    standalone_count = connection.scalar(
        sa.text("SELECT COUNT(*) FROM daily_leave_entries WHERE window_id IS NULL")
    )
    if standalone_count:
        raise RuntimeError("cannot downgrade while standalone daily leave records exist")
    op.drop_constraint(
        "ck_daily_leave_entries_source_time_shape",
        "daily_leave_entries",
        type_="check",
    )
    op.drop_column("daily_leave_entries", "end_at")
    op.drop_column("daily_leave_entries", "start_at")
    op.alter_column(
        "daily_leave_entries",
        "window_id",
        existing_type=sa.Integer(),
        existing_nullable=True,
        nullable=False,
    )
