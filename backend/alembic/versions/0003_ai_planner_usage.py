"""add persistent AI planner usage accounting

Revision ID: 0003_ai_planner_usage
Revises: 0002_operations_claiming
Create Date: 2026-09-27
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0003_ai_planner_usage"
down_revision: Union[str, Sequence[str], None] = "0002_operations_claiming"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "ai_planner_daily_usage",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("member_id", sa.Integer(), nullable=False),
        sa.Column("usage_date", sa.Date(), nullable=False),
        sa.Column("request_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("input_tokens", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("output_tokens", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("total_tokens", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("member_id", "usage_date", name="uq_ai_planner_usage_member_date"),
    )

def downgrade() -> None:
    op.drop_table("ai_planner_daily_usage")
