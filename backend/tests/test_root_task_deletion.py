"""MySQL-backed coverage for deleting a root item and its dependent records."""

from datetime import datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from unittest.mock import patch

from app.auth import get_current_member
from app.db import SessionLocal, get_db
from app.main import app
from app.models import (
    ItemActivity,
    ItemFact,
    Member,
    Task,
    item_fact_tasks,
    task_collaborators,
    task_dependencies,
)
from app.routers import tasks as tasks_router
from app.schemas import TaskCreate


def create_task(db, creator, *, title, parent_id=None, owner_id=None, collaborators=None, dependencies=None):
    created = tasks_router.create_task(
        TaskCreate(
            title=title,
            deliverable=f"{title}完成并可确认。",
            parent_id=parent_id,
            owner_id=owner_id,
            owner_claimable=False,
            collaborator_ids=collaborators or [],
            collaboration_open=True,
            deadline=datetime.now() + timedelta(days=3),
            status="todo",
            depends_on_task_ids=dependencies or [],
        ),
        current=creator,
        db=db,
    )
    return created.id


def count_for(db, table, *conditions):
    return db.scalar(select(func.count()).select_from(table).where(*conditions)) or 0


def main() -> None:
    target_roots: set[int] = set()
    target_children: set[int] = set()
    target_fact_ids: set[int] = set()
    target_activity_ids: set[int] = set()
    keep_roots: set[int] = set()
    keep_children: set[int] = set()
    keep_fact_ids: set[int] = set()
    keep_activity_ids: set[int] = set()

    with SessionLocal() as db:
        admin = db.scalar(select(Member).where(Member.email == "admin@example.com"))
        member = db.scalar(
            select(Member)
            .where(Member.role == "member", Member.status == "active")
            .order_by(Member.id)
            .limit(1)
        )
        assert admin and admin.status == "active" and admin.role == "admin"
        assert member and member.status == "active" and member.role == "member"

        target_root_id = create_task(db, admin, title="Root deletion smoke", owner_id=admin.id)
        target_roots.add(target_root_id)
        child_a_id = create_task(
            db, admin, title="Root deletion child A", parent_id=target_root_id, owner_id=admin.id,
        )
        child_b_id = create_task(
            db, admin, title="Root deletion child B", parent_id=target_root_id,
            owner_id=member.id, collaborators=[admin.id], dependencies=[child_a_id],
        )
        target_children.update((child_a_id, child_b_id))
        activity = ItemActivity(
            root_task_id=target_root_id,
            task_id=child_a_id,
            author_id=admin.id,
            content="Root deletion smoke activity",
        )
        db.add(activity)
        db.flush()
        target_activity_ids.add(activity.id)
        fact = tasks_router._create_item_fact(
            db,
            db.get(Task, target_root_id),
            admin,
            content="Root deletion smoke fact",
            scope="related",
            related_task_ids=[child_b_id],
            source_activity_id=activity.id,
        )
        target_fact_ids.add(fact.id)

        keep_root_id = create_task(db, admin, title="Keep unrelated root", owner_id=admin.id)
        keep_roots.add(keep_root_id)
        keep_child_id = create_task(
            db, admin, title="Keep unrelated child", parent_id=keep_root_id, owner_id=member.id,
        )
        keep_children.add(keep_child_id)
        keep_activity = ItemActivity(
            root_task_id=keep_root_id,
            task_id=keep_child_id,
            author_id=admin.id,
            content="Unrelated activity must remain",
        )
        db.add(keep_activity)
        db.flush()
        keep_activity_ids.add(keep_activity.id)
        keep_fact = tasks_router._create_item_fact(
            db,
            db.get(Task, keep_root_id),
            admin,
            content="Unrelated fact must remain",
            scope="related",
            related_task_ids=[keep_child_id],
            source_activity_id=keep_activity.id,
        )
        keep_fact_ids.add(keep_fact.id)
        db.commit()

        previous_overrides = dict(app.dependency_overrides)

        def override_database():
            yield db

        app.dependency_overrides[get_db] = override_database
        app.dependency_overrides[get_current_member] = lambda: admin
        try:
            client = TestClient(app)
            assert client.delete(f"/api/tasks/{child_a_id}").status_code == 400
            assert client.delete("/api/tasks/2147483000").status_code == 404
            assert db.get(Task, target_root_id) is not None

            app.dependency_overrides[get_current_member] = lambda: member
            assert client.delete(f"/api/tasks/{target_root_id}").status_code == 403
            assert db.get(Task, target_root_id) is not None

            # A failed commit must roll back child deletes and keep every relation.
            with patch.object(db, "commit", side_effect=RuntimeError("expected commit failure")):
                try:
                    tasks_router.delete_root_task(target_root_id, current=admin, db=db)
                except RuntimeError as exc:
                    assert str(exc) == "expected commit failure"
                else:
                    raise AssertionError("expected deletion commit to fail")
            db.expire_all()
            assert db.get(Task, target_root_id) is not None
            assert all(db.get(Task, child_id) is not None for child_id in target_children)
            assert count_for(db, ItemActivity, ItemActivity.id.in_(target_activity_ids)) == 1
            assert count_for(db, ItemFact, ItemFact.id.in_(target_fact_ids)) == 1
            assert count_for(db, item_fact_tasks, item_fact_tasks.c.fact_id.in_(target_fact_ids)) == 1
            assert count_for(db, task_dependencies, task_dependencies.c.task_id.in_(target_children)) == 1
            assert count_for(db, task_collaborators, task_collaborators.c.task_id.in_(target_children)) == 1

            app.dependency_overrides[get_current_member] = lambda: admin
            deleted = client.delete(f"/api/tasks/{target_root_id}")
            assert deleted.status_code == 204, deleted.text
            db.expire_all()
            assert db.get(Task, target_root_id) is None
            assert count_for(db, Task, Task.id.in_(target_children)) == 0
            assert count_for(db, ItemActivity, ItemActivity.id.in_(target_activity_ids)) == 0
            assert count_for(db, ItemFact, ItemFact.id.in_(target_fact_ids)) == 0
            assert count_for(db, item_fact_tasks, item_fact_tasks.c.fact_id.in_(target_fact_ids)) == 0
            assert count_for(db, task_dependencies, task_dependencies.c.task_id.in_(target_children)) == 0
            assert count_for(db, task_dependencies, task_dependencies.c.depends_on_task_id.in_(target_children)) == 0
            assert count_for(db, task_collaborators, task_collaborators.c.task_id.in_(target_children)) == 0

            # Another root's structure, history and current information are unchanged.
            assert db.get(Task, keep_root_id) is not None
            assert db.get(Task, keep_child_id) is not None
            assert count_for(db, ItemActivity, ItemActivity.id.in_(keep_activity_ids)) == 1
            assert count_for(db, ItemFact, ItemFact.id.in_(keep_fact_ids)) == 1
            assert count_for(db, item_fact_tasks, item_fact_tasks.c.fact_id.in_(keep_fact_ids)) == 1
        finally:
            app.dependency_overrides.clear()
            app.dependency_overrides.update(previous_overrides)
            all_roots = target_roots | keep_roots
            all_children = target_children | keep_children
            all_facts = target_fact_ids | keep_fact_ids
            all_activities = target_activity_ids | keep_activity_ids
            if all_facts:
                db.execute(delete(item_fact_tasks).where(item_fact_tasks.c.fact_id.in_(all_facts)))
                db.execute(delete(ItemFact).where(ItemFact.id.in_(all_facts)))
            if all_activities:
                db.execute(delete(ItemActivity).where(ItemActivity.id.in_(all_activities)))
            if all_children:
                db.execute(delete(Task).where(Task.id.in_(all_children)))
            if all_roots:
                db.execute(delete(Task).where(Task.id.in_(all_roots)))
            db.commit()
    print("Root task deletion tests passed")


if __name__ == "__main__":
    main()
