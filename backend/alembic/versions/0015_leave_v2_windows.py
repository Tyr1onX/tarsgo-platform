"""add authorized daily leave windows and generation snapshots

Revision ID: 0015_leave_v2_windows
Revises: 0014_camp_leave_v1
Create Date: 2026-10-06
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0015_leave_v2_windows"
down_revision: Union[str, Sequence[str], None] = "0014_camp_leave_v1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


COLLEGE_CODES = (
    "philosophy-sociology", "literature-journalism", "archaeology", "art", "physical-education",
    "foreign-languages-culture", "business-management", "law", "public-diplomacy", "marxism",
    "public-administration", "economics", "chemistry", "life-sciences", "mathematics", "physics",
    "mechanical-aerospace", "transport", "automotive", "bio-agricultural-engineering",
    "materials-science-engineering", "electronic-science-engineering", "integrated-circuits",
    "communications-engineering", "computer-science-technology", "software", "earth-sciences",
    "earth-exploration", "construction-engineering", "new-energy-environment",
    "instrumentation-electrical", "public-health", "bethune-first-clinical-medicine",
    "basic-medical-sciences", "bethune-stomatology", "pharmacy", "nursing", "veterinary-medicine",
    "plant-sciences", "animal-sciences", "food-science-engineering", "artificial-intelligence",
    "history-culture", "northeast-asia", "bionic-science-engineering",
)


def upgrade() -> None:
    op.create_table(
        "daily_leave_windows",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=100), nullable=False),
        sa.Column("start_at", sa.DateTime(), nullable=False),
        sa.Column("end_at", sa.DateTime(), nullable=False),
        sa.Column("open_until", sa.DateTime(), nullable=False),
        sa.Column("team_open", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column("public_enabled", sa.Boolean(), server_default=sa.text("0"), nullable=False),
        sa.Column("public_token", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="open", nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('open','closed')", name="ck_daily_leave_windows_status"),
        sa.CheckConstraint("start_at < end_at", name="ck_daily_leave_windows_time_order"),
        sa.CheckConstraint(
            "public_enabled = 0 OR public_token IS NOT NULL",
            name="ck_daily_leave_windows_public_token_required",
        ),
        sa.CheckConstraint(
            "public_enabled = 1 OR public_token IS NULL",
            name="ck_daily_leave_windows_public_token_disabled",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["members.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("public_token", name="uq_daily_leave_windows_public_token"),
    )
    op.create_index(
        "ix_daily_leave_windows_status_open_until",
        "daily_leave_windows",
        ["status", "open_until"],
    )

    op.create_table(
        "daily_leave_entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("window_id", sa.Integer(), nullable=False),
        sa.Column("member_id", sa.Integer(), nullable=True),
        sa.Column("name_snapshot", sa.String(length=50), nullable=False),
        sa.Column("student_id_snapshot", sa.String(length=8), nullable=False),
        sa.Column("college_snapshot", sa.String(length=50), nullable=False),
        sa.Column("participant_type", sa.String(length=20), nullable=False),
        sa.Column("submitted_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "participant_type IN ('formal','reserve','other')",
            name="ck_daily_leave_entries_participant_type",
        ),
        sa.CheckConstraint("CHAR_LENGTH(name_snapshot) BETWEEN 2 AND 50", name="ck_daily_leave_entries_name_length"),
        sa.CheckConstraint("CHAR_LENGTH(student_id_snapshot) = 8", name="ck_daily_leave_entries_student_id_length"),
        sa.CheckConstraint(
            "college_snapshot IN (" + ",".join(f"'{code}'" for code in COLLEGE_CODES) + ")",
            name="ck_daily_leave_entries_college",
        ),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["window_id"], ["daily_leave_windows.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("window_id", "student_id_snapshot", name="uq_daily_leave_window_student"),
        sa.UniqueConstraint("window_id", "member_id", name="uq_daily_leave_window_member"),
    )
    op.create_index(
        "ix_daily_leave_entries_window_college",
        "daily_leave_entries",
        ["window_id", "college_snapshot"],
    )


def downgrade() -> None:
    op.drop_index("ix_daily_leave_entries_window_college", table_name="daily_leave_entries")
    op.drop_table("daily_leave_entries")
    op.drop_index("ix_daily_leave_windows_status_open_until", table_name="daily_leave_windows")
    op.drop_table("daily_leave_windows")
