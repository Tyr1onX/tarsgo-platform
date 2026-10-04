"""add school leave v1

Revision ID: 0010_school_leave_v1
Revises: 0009_optional_task_deadlines
Create Date: 2026-10-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0010_school_leave_v1"
down_revision: Union[str, Sequence[str], None] = "0009_optional_task_deadlines"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("members", sa.Column("student_id", sa.String(length=50), nullable=True))
    op.create_unique_constraint("uq_members_student_id", "members", ["student_id"])

    op.create_table(
        "school_leave_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("collected_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("sent_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint(
            "status IN ('ready','sent','cancelled')",
            name="ck_school_leave_runs_status",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["members.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["sent_by"], ["members.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_school_leave_runs_status_collected",
        "school_leave_runs",
        ["status", "collected_at"],
        unique=False,
    )

    op.create_table(
        "school_leave_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("member_id", sa.Integer(), nullable=False),
        sa.Column("start_at", sa.DateTime(), nullable=False),
        sa.Column("end_at", sa.DateTime(), nullable=False),
        sa.Column("member_name_snapshot", sa.String(length=100), nullable=False),
        sa.Column("student_id_snapshot", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending','included','withdrawn')",
            name="ck_school_leave_requests_status",
        ),
        sa.CheckConstraint("start_at < end_at", name="ck_school_leave_requests_time_order"),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"]),
        sa.ForeignKeyConstraint(["run_id"], ["school_leave_runs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_school_leave_requests_status_created",
        "school_leave_requests",
        ["status", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_school_leave_requests_run",
        "school_leave_requests",
        ["run_id"],
        unique=False,
    )
    op.create_index(
        "ix_school_leave_requests_member_created",
        "school_leave_requests",
        ["member_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_school_leave_requests_member_created", table_name="school_leave_requests")
    op.drop_index("ix_school_leave_requests_run", table_name="school_leave_requests")
    op.drop_index("ix_school_leave_requests_status_created", table_name="school_leave_requests")
    op.drop_table("school_leave_requests")
    op.drop_index("ix_school_leave_runs_status_collected", table_name="school_leave_runs")
    op.drop_table("school_leave_runs")
    op.drop_constraint("uq_members_student_id", "members", type_="unique")
    op.drop_column("members", "student_id")
