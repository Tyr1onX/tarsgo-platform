"""add optional college and team membership identity fields

Revision ID: 0013_member_identity
Revises: 0012_school_leave_completion
Create Date: 2026-10-06
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0013_member_identity"
down_revision: Union[str, Sequence[str], None] = "0012_school_leave_completion"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


COLLEGE_CODES = (
    "philosophy-sociology",
    "literature-journalism",
    "archaeology",
    "art",
    "physical-education",
    "foreign-languages-culture",
    "business-management",
    "law",
    "public-diplomacy",
    "marxism",
    "public-administration",
    "economics",
    "chemistry",
    "life-sciences",
    "mathematics",
    "physics",
    "mechanical-aerospace",
    "transport",
    "automotive",
    "bio-agricultural-engineering",
    "materials-science-engineering",
    "electronic-science-engineering",
    "integrated-circuits",
    "communications-engineering",
    "computer-science-technology",
    "software",
    "earth-sciences",
    "earth-exploration",
    "construction-engineering",
    "new-energy-environment",
    "instrumentation-electrical",
    "public-health",
    "bethune-first-clinical-medicine",
    "basic-medical-sciences",
    "bethune-stomatology",
    "pharmacy",
    "nursing",
    "veterinary-medicine",
    "plant-sciences",
    "animal-sciences",
    "food-science-engineering",
    "artificial-intelligence",
    "history-culture",
    "northeast-asia",
    "bionic-science-engineering",
)


def upgrade() -> None:
    op.add_column("members", sa.Column("college", sa.String(length=50), nullable=True))
    op.add_column("members", sa.Column("team_membership", sa.String(length=20), nullable=True))
    codes = ",".join(f"'{code}'" for code in COLLEGE_CODES)
    op.create_check_constraint(
        "ck_members_college",
        "members",
        f"college IS NULL OR college IN ({codes})",
    )
    op.create_check_constraint(
        "ck_members_team_membership",
        "members",
        "team_membership IS NULL OR team_membership IN ('formal','reserve')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_members_team_membership", "members", type_="check")
    op.drop_constraint("ck_members_college", "members", type_="check")
    op.drop_column("members", "team_membership")
    op.drop_column("members", "college")
