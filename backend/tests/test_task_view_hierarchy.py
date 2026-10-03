"""MySQL-backed checks that scoped task lists retain their root-item context."""

from datetime import datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.auth import get_current_member
from app.db import SessionLocal, get_db
from app.main import app
from app.models import Member, Task
from app.routers import tasks as tasks_router
from app.schemas import TaskCreate


def create_task(db, creator, *, title, parent_id=None, owner_id=None, claimable=False):
    task = tasks_router.create_task(
        TaskCreate(
            title=title,
            deliverable=f"{title}完成并可验收。",
            parent_id=parent_id,
            owner_id=owner_id,
            owner_claimable=claimable,
            collaborator_ids=[],
            collaboration_open=False,
            deadline=datetime.now() + timedelta(days=3),
            status="todo",
            depends_on_task_ids=[],
        ),
        current=creator,
        db=db,
    )
    return task.id


def main() -> None:
    root_ids: set[int] = set()
    child_ids: set[int] = set()
    with SessionLocal() as db:
        admin = db.scalar(select(Member).where(Member.email == "admin@example.com"))
        manager = db.scalar(select(Member).where(Member.email == "manager@example.com"))
        member = db.scalar(
            select(Member)
            .where(Member.role == "member", Member.status == "active")
            .order_by(Member.id)
            .limit(1)
        )
        assert admin and manager and member

        root_a = create_task(db, manager, title="Hierarchy claim smoke A", owner_id=manager.id)
        root_ids.add(root_a)
        claim_a = create_task(db, manager, title="Claimable child A1", parent_id=root_a, claimable=True)
        claim_b = create_task(db, manager, title="Claimable child A2", parent_id=root_a, claimable=True)
        assigned = create_task(db, manager, title="Assigned child A3", parent_id=root_a, owner_id=member.id)
        child_ids.update((claim_a, claim_b, assigned))

        root_b = create_task(db, manager, title="Hierarchy claim smoke B", owner_id=admin.id)
        root_ids.add(root_b)
        claim_c = create_task(db, manager, title="Claimable child B1", parent_id=root_b, claimable=True)
        child_ids.add(claim_c)

        standalone_claimable_root = create_task(
            db, manager, title="Standalone claimable root", claimable=True,
        )
        root_ids.add(standalone_claimable_root)
        db.commit()

        previous_overrides = dict(app.dependency_overrides)

        def override_database():
            yield db

        app.dependency_overrides[get_db] = override_database
        app.dependency_overrides[get_current_member] = lambda: member
        try:
            client = TestClient(app)
            claimable_response = client.get("/api/tasks?scope=claimable")
            assert claimable_response.status_code == 200, claimable_response.text
            claimable_rows = claimable_response.json()
            claimable_by_id = {row["id"]: row for row in claimable_rows}
            assert {root_a, root_b, standalone_claimable_root, claim_a, claim_b, claim_c} <= set(claimable_by_id)
            assert assigned not in claimable_by_id
            assert sum(row["id"] == root_a for row in claimable_rows) == 1
            assert claimable_by_id[root_a]["owner"]["id"] == manager.id
            assert claimable_by_id[root_a]["owner_claimable"] is False
            assert claimable_by_id[standalone_claimable_root]["parent_id"] is None
            assert claimable_by_id[standalone_claimable_root]["owner_claimable"] is True

            mine_response = client.get("/api/tasks?scope=mine")
            assert mine_response.status_code == 200, mine_response.text
            mine_rows = mine_response.json()
            mine_by_id = {row["id"]: row for row in mine_rows}
            assert root_a in mine_by_id
            assert assigned in mine_by_id
            assert claim_a not in mine_by_id and claim_b not in mine_by_id
            assert root_b not in mine_by_id
            assert sum(row["id"] == root_a for row in mine_rows) == 1
        finally:
            app.dependency_overrides.clear()
            app.dependency_overrides.update(previous_overrides)
            if child_ids:
                db.execute(delete(Task).where(Task.id.in_(child_ids)))
            if root_ids:
                db.execute(delete(Task).where(Task.id.in_(root_ids)))
            db.commit()
    print("Scoped task view parent hierarchy tests passed")


if __name__ == "__main__":
    main()
