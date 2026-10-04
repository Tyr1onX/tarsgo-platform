"""add team groups, simplify roles, and add registration windows

Revision ID: 0011_team_registration
Revises: 0010_school_leave_v1
Create Date: 2026-10-04
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0011_team_registration"
down_revision: Union[str, Sequence[str], None] = "0010_school_leave_v1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()
    manager_count = connection.scalar(
        sa.text("SELECT COUNT(*) FROM members WHERE role = 'manager'")
    )
    if manager_count:
        raise RuntimeError(
            "members with role=manager exist; map them to admin/member before this migration"
        )

    op.add_column("members", sa.Column("team_group", sa.String(length=20), nullable=True))
    op.create_check_constraint(
        "ck_members_team_group",
        "members",
        "team_group IS NULL OR team_group IN ('electrical','mechanical','vision','ai','operations')",
    )
    op.drop_constraint("ck_members_role", "members", type_="check")
    op.create_check_constraint(
        "ck_members_role",
        "members",
        "role IN ('admin','member')",
    )

    op.create_table(
        "team_registration_windows",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["created_by"], ["members.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )


def downgrade() -> None:
    op.drop_table("team_registration_windows")
    op.drop_constraint("ck_members_role", "members", type_="check")
    op.create_check_constraint(
        "ck_members_role",
        "members",
        "role IN ('admin','manager','member')",
    )
    op.drop_constraint("ck_members_team_group", "members", type_="check")
    op.drop_column("members", "team_group")
