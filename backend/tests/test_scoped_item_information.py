"""MySQL-backed coverage for scoped current facts and task-owned history."""

import os
import uuid
from datetime import datetime, timedelta
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import delete, select

from app.ai_planner import PlannerFactExtractionGeneration
from app.db import SessionLocal
from app.models import ItemActivity, ItemFact, Member, Task
from app.routers import ai_items, tasks as tasks_router
from app.schemas import (
    AIItemFactExtractionOut,
    AIItemFactExtractionRequest,
    AIItemFactSuggestion,
    ItemFactCreate,
    ItemFactScopeUpdate,
    TaskCreate,
)


class FactProvider:
    def __init__(self, suggestions):
        self.suggestions = suggestions
        self.calls = 0
        self.context = ""

    def extract_facts(self, context):
        self.calls += 1
        self.context = context
        return PlannerFactExtractionGeneration(
            extraction=AIItemFactExtractionOut(suggestions=self.suggestions),
            input_tokens=17,
            output_tokens=11,
            total_tokens=28,
        )


def expect_http(expected, callback):
    try:
        callback()
    except HTTPException as exc:
        assert exc.status_code == expected, (exc.status_code, exc.detail)
        return
    raise AssertionError(f"expected HTTP {expected}")


def create_task(db, manager, *, title, parent_id=None, owner_id=None, claimable=False,
                collaborators=None, dependencies=None):
    result = tasks_router.create_task(
        TaskCreate(
            title=title,
            deliverable=f"{title}完成并可确认。",
            parent_id=parent_id,
            owner_id=owner_id,
            owner_claimable=claimable,
            collaborator_ids=collaborators or [],
            collaboration_open=True,
            deadline=datetime.now() + timedelta(days=2),
            depends_on_task_ids=dependencies or [],
        ),
        current=manager,
        db=db,
    )
    return result.id


def main():
    token = uuid.uuid4().hex[:12]
    root_ids: set[int] = set()
    child_ids: set[int] = set()
    member_ids: set[int] = set()
    try:
        with SessionLocal() as db:
            manager = db.scalar(select(Member).where(Member.email == "manager@example.com"))
            assert manager and manager.status == "active"
            claimant = Member(name=f"Scoped Claimant {token}", email=f"scoped-claim-{token}@example.invalid", role="member", status="active")
            collaborator = Member(name=f"Scoped Collaborator {token}", email=f"scoped-collab-{token}@example.invalid", role="member", status="active")
            unrelated = Member(name=f"Scoped Unrelated {token}", email=f"scoped-outside-{token}@example.invalid", role="member", status="active")
            db.add_all([claimant, collaborator, unrelated])
            db.commit()
            db.refresh(claimant)
            db.refresh(collaborator)
            db.refresh(unrelated)
            member_ids.update((claimant.id, collaborator.id, unrelated.id))

            root_id = create_task(db, manager, title=f"Scoped Smoke Root {token}", owner_id=manager.id)
            root_ids.add(root_id)
            task_a = create_task(db, manager, title="确认时间地点", parent_id=root_id, owner_id=manager.id)
            task_b = create_task(db, manager, title="准备参观路线", parent_id=root_id, claimable=True, dependencies=[task_a])
            task_c = create_task(db, manager, title="准备展示设备", parent_id=root_id, owner_id=manager.id, collaborators=[collaborator.id])
            task_d = create_task(db, manager, title="归档活动资料", parent_id=root_id, owner_id=unrelated.id)
            task_e = create_task(db, manager, title="准备接待资料", parent_id=root_id, owner_id=claimant.id)
            child_ids.update((task_a, task_b, task_c, task_d, task_e))
            other_root = create_task(db, manager, title=f"Other Scoped Root {token}", owner_id=manager.id)
            root_ids.add(other_root)
            other_child = create_task(db, manager, title="其他事项任务", parent_id=other_root, owner_id=manager.id)
            child_ids.add(other_child)

            activity_b = ItemActivity(root_task_id=root_id, task_id=task_b, author_id=manager.id, content="参观路线的门禁信息已确认。")
            db.add(activity_b)
            db.flush()
            global_fact = tasks_router._create_item_fact(db, db.get(Task, root_id), manager, content="活动时间为周三 14:00。", scope="global")
            route_fact = tasks_router._create_item_fact(
                db, db.get(Task, root_id), manager,
                content="来访团队从东门进入。", scope="related", related_task_ids=[task_b],
                source_activity_id=activity_b.id,
            )
            db.commit()

            # Global facts are visible to all; a scoped fact is visible only to that task's participants.
            assert "活动时间为周三 14:00。" in tasks_router.get_task(task_d, current=unrelated, db=db).context_facts
            assert "来访团队从东门进入。" not in tasks_router.get_task(task_d, current=unrelated, db=db).context_facts
            assert "来访团队从东门进入。" not in tasks_router.get_task(task_b, current=claimant, db=db).context_facts
            assert "来访团队从东门进入。" in tasks_router.get_task(root_id, current=manager, db=db).context_facts
            assert "来访团队从东门进入。" not in tasks_router.get_task(root_id, current=unrelated, db=db).context_facts
            assert all(row.id != activity_b.id for row in tasks_router.list_item_activities(
                root_id, task_id=task_b, current=claimant, db=db,
            ))
            # A member may participate in multiple assignments; the selected
            # task page must still exclude another assignment's history.
            assert all(row.id != activity_b.id for row in tasks_router.list_item_activities(
                root_id, task_id=task_e, current=claimant, db=db,
            ))

            claimed = tasks_router.claim_task_owner(task_b, current=claimant, db=db)
            assert "来访团队从东门进入。" in claimed.context_facts
            assert any(item.id == route_fact.id for item in claimed.item_facts)
            assert any(row.id == activity_b.id for row in tasks_router.list_item_activities(root_id, current=claimant, db=db))
            assert any(row.id == activity_b.id for row in tasks_router.list_item_activities(
                root_id, task_id=task_b, current=claimant, db=db,
            ))
            # Task D is a different execution context even when a member can
            # still read its structure; B's history must stay scoped to B.
            assert all(row.id != activity_b.id for row in tasks_router.list_item_activities(
                root_id, task_id=task_d, current=claimant, db=db,
            ))
            assert any(row.id == activity_b.id for row in tasks_router.list_item_activities(root_id, current=manager, db=db))
            assert all(row.id != activity_b.id for row in tasks_router.list_item_activities(root_id, current=unrelated, db=db))

            # A new owner inherits the work's prior scoped context; unclaim removes it from their view.
            tasks_router.unclaim_task_owner(task_b, current=claimant, db=db)
            assert "来访团队从东门进入。" not in tasks_router.get_task(task_b, current=claimant, db=db).context_facts
            assert all(row.id != activity_b.id for row in tasks_router.list_item_activities(root_id, current=claimant, db=db))
            assert all(row.id != activity_b.id for row in tasks_router.list_item_activities(
                root_id, task_id=task_b, current=claimant, db=db,
            ))
            tasks_router.claim_task_owner(task_b, current=claimant, db=db)

            # Collaborators receive the task's scoped fact while a different task owner does not.
            fact_c = tasks_router._create_item_fact(
                db, db.get(Task, root_id), manager,
                content="展示设备需从北侧入口搬运。", scope="related", related_task_ids=[task_c],
            )
            db.commit()
            assert "展示设备需从北侧入口搬运。" in tasks_router.get_task(task_c, current=collaborator, db=db).context_facts
            assert "展示设备需从北侧入口搬运。" not in tasks_router.get_task(task_d, current=unrelated, db=db).context_facts
            manager_root = tasks_router.get_task(root_id, current=manager, db=db)
            assert {fact.id for fact in manager_root.item_facts} >= {global_fact.id, route_fact.id, fact_c.id}

            # AI extraction suggests scope, task targets and a possible replacement; it never writes a fact.
            progress = ItemActivity(root_task_id=root_id, task_id=task_b, author_id=claimant.id, content="已确认周三 14:30 到达，参观路线从东门开始。")
            db.add(progress)
            db.commit()
            db.refresh(progress)
            provider = FactProvider([
                AIItemFactSuggestion(
                    text="来访团队周三 14:30 从东门进入。",
                    reason="更新确认了时间和入口。",
                    scope="related",
                    related_task_ids=[task_b, task_c, task_d, other_child],
                    supersedes_fact_id=route_fact.id,
                )
            ])
            with patch.dict(os.environ, {"AI_PLANNER_ENABLED": "true", "AI_API_KEY": "ci-placeholder", "AI_MODEL": "ci-placeholder"}):
                extracted = ai_items.extract_activity_facts(
                    root_id,
                    AIItemFactExtractionRequest(activity_id=progress.id),
                    current=claimant,
                    db=db,
                    provider=provider,
                )
            assert provider.calls == 1
            suggestion = extracted.suggestions[0]
            assert suggestion.scope == "related"
            assert suggestion.related_task_ids == [task_b, task_c, task_d]
            assert suggestion.supersedes_fact_id == route_fact.id
            assert str(task_a) in provider.context and str(task_c) in provider.context
            assert claimant.email not in provider.context and collaborator.email not in provider.context
            assert db.get(ItemFact, route_fact.id).is_active is True
            assert db.scalar(select(ItemFact.id).where(ItemFact.root_task_id == root_id, ItemFact.content == suggestion.text)) is None

            empty_provider = FactProvider([])
            with patch.dict(os.environ, {"AI_PLANNER_ENABLED": "true", "AI_API_KEY": "ci-placeholder", "AI_MODEL": "ci-placeholder"}):
                empty_extracted = ai_items.extract_activity_facts(
                    root_id,
                    AIItemFactExtractionRequest(activity_id=progress.id),
                    current=claimant,
                    db=db,
                    provider=empty_provider,
                )
            assert empty_provider.calls == 1
            assert empty_extracted.suggestions == []
            assert db.scalar(select(ItemFact.id).where(ItemFact.root_task_id == root_id, ItemFact.content == suggestion.text)) is None

            # Applying a superseding fact makes the old fact inactive but preserves its source activity.
            tasks_router.add_context_fact(
                root_id,
                ItemFactCreate(
                    content=suggestion.text,
                    scope="related",
                    related_task_ids=[task_b],
                    source_activity_id=progress.id,
                    supersedes_fact_id=route_fact.id,
                ),
                current=manager,
                db=db,
            )
            db.expire_all()
            old_fact = db.get(ItemFact, route_fact.id)
            assert old_fact.is_active is False and old_fact.superseded_by_id is not None
            assert db.get(ItemActivity, activity_b.id) is not None
            assert suggestion.text in tasks_router.get_task(task_b, current=claimant, db=db).context_facts
            assert "来访团队从东门进入。" not in tasks_router.get_task(task_b, current=claimant, db=db).context_facts
            assert any(row.id == activity_b.id for row in tasks_router.list_item_activities(root_id, current=claimant, db=db))

            # Members cannot rewrite scope or replace an existing fact; manager/root owner can.
            expect_http(403, lambda: tasks_router.update_item_fact_scope(
                root_id, fact_c.id, ItemFactScopeUpdate(scope="global", related_task_ids=[]), current=collaborator, db=db,
            ))
            expect_http(422, lambda: tasks_router.add_context_fact(
                root_id,
                ItemFactCreate(content="跨事项错误关联", scope="related", related_task_ids=[task_b + 99999]),
                current=manager,
                db=db,
            ))
            expect_http(422, lambda: tasks_router.add_context_fact(
                root_id,
                ItemFactCreate(content="关联到其他事项", scope="related", related_task_ids=[other_child]),
                current=manager,
                db=db,
            ))
            tasks_router.update_item_fact_scope(
                root_id, fact_c.id, ItemFactScopeUpdate(scope="global", related_task_ids=[]), current=manager, db=db,
            )
            assert "展示设备需从北侧入口搬运。" in tasks_router.get_task(task_d, current=unrelated, db=db).context_facts
    finally:
        with SessionLocal() as db:
            if root_ids:
                db.execute(delete(ItemFact).where(ItemFact.root_task_id.in_(root_ids)))
                db.execute(delete(ItemActivity).where(ItemActivity.root_task_id.in_(root_ids)))
                if child_ids:
                    db.execute(delete(Task).where(Task.id.in_(child_ids)))
                db.execute(delete(Task).where(Task.id.in_(root_ids)))
            if member_ids:
                db.execute(delete(Member).where(Member.id.in_(member_ids)))
            db.commit()
    print("Scoped item information tests passed")


if __name__ == "__main__":
    main()
