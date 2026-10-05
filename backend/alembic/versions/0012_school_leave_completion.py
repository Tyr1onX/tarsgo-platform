"""add school leave completion loop

Revision ID: 0012_school_leave_completion
Revises: 0011_team_registration
Create Date: 2026-10-05
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0012_school_leave_completion"
down_revision: Union[str, Sequence[str], None] = "0011_team_registration"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("school_leave_runs", sa.Column("downloaded_at", sa.DateTime(), nullable=True))
    op.add_column("school_leave_runs", sa.Column("downloaded_by", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_school_leave_runs_downloaded_by_members",
        "school_leave_runs",
        "members",
        ["downloaded_by"],
        ["id"],
        ondelete="SET NULL",
    )

    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            UPDATE school_leave_runs
            SET downloaded_at = COALESCE(sent_at, collected_at),
                downloaded_by = sent_by
            WHERE status = 'sent'
            """
        )
    )

    op.drop_constraint("ck_school_leave_runs_status", "school_leave_runs", type_="check")
    connection.execute(
        sa.text("UPDATE school_leave_runs SET status = 'awaiting_return' WHERE status = 'sent'")
    )
    op.create_check_constraint(
        "ck_school_leave_runs_status",
        "school_leave_runs",
        "status IN ('ready','awaiting_return','completed','cancelled')",
    )

    op.create_table(
        "school_leave_group_results",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("group_index", sa.Integer(), nullable=False),
        sa.Column("stored_name", sa.String(length=100), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=50), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("uploaded_by", sa.Integer(), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["school_leave_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploaded_by"], ["members.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "run_id",
            "group_index",
            name="uq_school_leave_group_results_run_group",
        ),
    )
    op.create_index(
        "ix_school_leave_group_results_cleanup",
        "school_leave_group_results",
        ["expires_at", "deleted_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_school_leave_group_results_cleanup",
        table_name="school_leave_group_results",
    )
    op.drop_table("school_leave_group_results")

    connection = op.get_bind()
    op.drop_constraint("ck_school_leave_runs_status", "school_leave_runs", type_="check")
    connection.execute(
        sa.text(
            """
            UPDATE school_leave_runs
            SET status = 'sent',
                sent_at = COALESCE(sent_at, downloaded_at),
                sent_by = COALESCE(sent_by, downloaded_by)
            WHERE status IN ('awaiting_return','completed')
            """
        )
    )
    op.create_check_constraint(
        "ck_school_leave_runs_status",
        "school_leave_runs",
        "status IN ('ready','sent','cancelled')",
    )

    op.drop_constraint(
        "fk_school_leave_runs_downloaded_by_members",
        "school_leave_runs",
        type_="foreignkey",
    )
    op.drop_column("school_leave_runs", "downloaded_by")
    op.drop_column("school_leave_runs", "downloaded_at")
