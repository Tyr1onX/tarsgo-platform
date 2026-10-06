"""add independent winter and summer camp leave collection

Revision ID: 0014_camp_leave_v1
Revises: 0013_member_identity
Create Date: 2026-10-06
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0014_camp_leave_v1"
down_revision: Union[str, Sequence[str], None] = "0013_member_identity"
branch_labels = None
depends_on = None


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
        "camp_leave_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("title", sa.String(length=100), nullable=False),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("collection_deadline", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="collecting", nullable=False),
        sa.Column("public_token", sa.String(length=64), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("type IN ('winter','summer')", name="ck_camp_leave_events_type"),
        sa.CheckConstraint("status IN ('collecting','closed')", name="ck_camp_leave_events_status"),
        sa.CheckConstraint("start_date <= end_date", name="ck_camp_leave_events_date_order"),
        sa.ForeignKeyConstraint(["created_by"], ["members.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("public_token", name="uq_camp_leave_events_public_token"),
    )
    op.create_index(
        "ix_camp_leave_events_status_deadline",
        "camp_leave_events",
        ["status", "collection_deadline"],
        unique=False,
    )

    college_codes = ",".join(f"'{code}'" for code in COLLEGE_CODES)
    op.create_table(
        "camp_leave_participants",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("member_id", sa.Integer(), nullable=True),
        sa.Column("name_snapshot", sa.String(length=50), nullable=False),
        sa.Column("student_id_snapshot", sa.String(length=8), nullable=False),
        sa.Column("college_snapshot", sa.String(length=50), nullable=False),
        sa.Column("participant_type", sa.String(length=20), nullable=False),
        sa.Column("submitted_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint(
            "participant_type IN ('formal','reserve','other')",
            name="ck_camp_leave_participants_type",
        ),
        sa.CheckConstraint(
            "CHAR_LENGTH(name_snapshot) BETWEEN 2 AND 50",
            name="ck_camp_leave_participants_name_length",
        ),
        sa.CheckConstraint(
            "CHAR_LENGTH(student_id_snapshot) = 8",
            name="ck_camp_leave_participants_student_id",
        ),
        sa.CheckConstraint(
            f"college_snapshot IN ({college_codes})",
            name="ck_camp_leave_participants_college",
        ),
        sa.ForeignKeyConstraint(["event_id"], ["camp_leave_events.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", "student_id_snapshot", name="uq_camp_leave_event_student"),
        sa.UniqueConstraint("event_id", "member_id", name="uq_camp_leave_event_member"),
    )
    op.create_index(
        "ix_camp_leave_participants_event_college",
        "camp_leave_participants",
        ["event_id", "college_snapshot"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_camp_leave_participants_event_college", table_name="camp_leave_participants")
    op.drop_table("camp_leave_participants")
    op.drop_index("ix_camp_leave_events_status_deadline", table_name="camp_leave_events")
    op.drop_table("camp_leave_events")
