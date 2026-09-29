"""replace root JSON facts with scoped item facts

Revision ID: 0008_scoped_item_information
Revises: 0007_shared_execution_scene
Create Date: 2026-09-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0008_scoped_item_information"
down_revision: Union[str, Sequence[str], None] = "0007_shared_execution_scene"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "item_facts",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("root_task_id", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("scope", sa.String(length=20), nullable=False),
        sa.Column("source_activity_id", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("superseded_by_id", sa.Integer(), nullable=True),
        sa.Column("superseded_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("scope IN ('global','related')", name="ck_item_facts_scope"),
        sa.ForeignKeyConstraint(["root_task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_activity_id"], ["item_activities.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["members.id"]),
        sa.ForeignKeyConstraint(["superseded_by_id"], ["item_facts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_item_facts_root_active", "item_facts", ["root_task_id", "is_active", "created_at"])
    op.create_table(
        "item_fact_tasks",
        sa.Column("fact_id", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["fact_id"], ["item_facts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("fact_id", "task_id"),
    )
    op.create_index("ix_item_fact_tasks_task_id", "item_fact_tasks", ["task_id"])

    bind = op.get_bind()
    tasks = sa.table(
        "tasks",
        sa.column("id", sa.Integer()),
        sa.column("created_by", sa.Integer()),
        sa.column("parent_id", sa.Integer()),
        sa.column("context_facts", sa.JSON()),
    )
    facts = sa.table(
        "item_facts",
        sa.column("root_task_id", sa.Integer()),
        sa.column("content", sa.Text()),
        sa.column("scope", sa.String(20)),
        sa.column("created_by", sa.Integer()),
        sa.column("is_active", sa.Boolean()),
    )
    for task in bind.execute(sa.select(tasks.c.id, tasks.c.created_by, tasks.c.parent_id, tasks.c.context_facts)):
        if task.parent_id is not None:
            continue
        for content in task.context_facts or []:
            if not isinstance(content, str) or not content.strip():
                continue
            bind.execute(
                facts.insert().values(
                    root_task_id=task.id,
                    content=content,
                    scope="global",
                    created_by=task.created_by,
                    is_active=True,
                )
            )

    with op.batch_alter_table("tasks") as batch_op:
        batch_op.drop_column("context_facts")


def downgrade() -> None:
    op.add_column(
        "tasks",
        sa.Column("context_facts", sa.JSON(), server_default=sa.text("(JSON_ARRAY())"), nullable=False),
    )
    bind = op.get_bind()
    tasks = sa.table("tasks", sa.column("id", sa.Integer()), sa.column("context_facts", sa.JSON()))
    facts = sa.table(
        "item_facts",
        sa.column("root_task_id", sa.Integer()),
        sa.column("content", sa.Text()),
        sa.column("scope", sa.String(20)),
        sa.column("is_active", sa.Boolean()),
        sa.column("created_at", sa.DateTime()),
        sa.column("id", sa.Integer()),
    )
    grouped: dict[int, list[str]] = {}
    for row in bind.execute(
        sa.select(facts.c.root_task_id, facts.c.content)
        .where(facts.c.scope == "global", facts.c.is_active.is_(True))
        .order_by(facts.c.created_at, facts.c.id)
    ):
        grouped.setdefault(row.root_task_id, []).append(row.content)
    for root_id, content in grouped.items():
        bind.execute(tasks.update().where(tasks.c.id == root_id).values(context_facts=content))

    op.drop_index("ix_item_fact_tasks_task_id", table_name="item_fact_tasks")
    op.drop_table("item_fact_tasks")
    op.drop_index("ix_item_facts_root_active", table_name="item_facts")
    op.drop_table("item_facts")
