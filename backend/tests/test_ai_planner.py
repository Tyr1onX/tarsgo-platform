import os
from datetime import datetime
from unittest.mock import patch

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai_planner import PlannerGeneration, PlannerInvalidResponse
from app.db import SessionLocal
from app.models import AIPlannerDailyUsage, Member, Task
from app.routers import ai_planner as planner_router
from app.routers import tasks as tasks_router
from app.schemas import AIPlannerDraft, AIPlannerItemDraft, AIPlannerRequest, AIPlannerTaskDraft, TaskBatchCreate, TaskBatchItemIn


class FakeProvider:
    def __init__(self):
        self.calls = 0
    def generate(self, description: str) -> PlannerGeneration:
        self.calls += 1
        return PlannerGeneration(
            draft=AIPlannerDraft(
                item=AIPlannerItemDraft(title="小学科技展", deliverable="完成现场展示并收齐活动素材。", deadline=None),
                tasks=[
                    AIPlannerTaskDraft(title="机器人与展示设备准备", deliverable="设备可正常展示并完成装车。", owner_claimable=True, collaboration_open=False),
                    AIPlannerTaskDraft(title="现场摄影", deliverable="原图完整上传。", owner_claimable=True, collaboration_open=True),
                    AIPlannerTaskDraft(title="活动资料归档", deliverable="素材按活动归档。", owner_claimable=True, collaboration_open=False),
                ],
                questions=["活动当天的最终结束时间是什么？"],
            ),
            input_tokens=120, output_tokens=180, total_tokens=300,
        )


class InvalidProvider:
    def generate(self, description: str) -> PlannerGeneration:
        raise PlannerInvalidResponse


def expect_http(expected: int, callback) -> None:
    try:
        callback()
    except HTTPException as exc:
        assert exc.status_code == expected, (exc.status_code, exc.detail)
        return
    raise AssertionError(f"expected HTTP {expected}")


def main() -> None:
    with SessionLocal() as db:
        admin = db.scalar(select(Member).where(Member.email == "admin@example.com"))
        manager = db.scalar(select(Member).where(Member.email == "manager@example.com"))
        assert admin is not None and manager is not None
        os.environ.update({
            "AI_PLANNER_ENABLED": "true",
            "AI_PLANNER_ALLOWED_MEMBER_IDS": str(admin.id),
            "AI_API_KEY": "ci-placeholder",
            "AI_MODEL": "ci-placeholder",
        })

        extra_admin = Member(name="测试管理员", email="planner-extra-admin@example.com", password_hash=None, role="admin", status="active")
        db.add(extra_admin)
        db.commit()

        request = AIPlannerRequest(description="准备一次校园科技展示，需要展示、摄影和资料整理。")
        expect_http(403, lambda: planner_router.generate_plan(request, current=manager, db=db, provider=FakeProvider()))
        expect_http(403, lambda: planner_router.generate_plan(request, current=extra_admin, db=db, provider=FakeProvider()))

        saved_key = os.environ.pop("AI_API_KEY")
        expect_http(503, lambda: planner_router.generate_plan(request, current=admin, db=db, provider=FakeProvider()))
        os.environ["AI_API_KEY"] = saved_key

        try:
            AIPlannerRequest(description="字" * 5001)
        except ValidationError:
            pass
        else:
            raise AssertionError("overlong planner input should fail")

        before = db.scalar(select(func.count(Task.id))) or 0
        provider = FakeProvider()
        draft = planner_router.generate_plan(request, current=admin, db=db, provider=provider)
        after = db.scalar(select(func.count(Task.id))) or 0
        assert provider.calls == 1 and before == after
        assert not hasattr(draft.tasks[0], "owner_id")

        expect_http(502, lambda: planner_router.generate_plan(request, current=admin, db=db, provider=InvalidProvider()))

        draft.item.title = "小学科技展（人工确认）"
        draft.item.deliverable = "完成展示，并在当天收齐现场素材。"
        draft.item.deadline = datetime(2026, 10, 12, 18, 0)
        draft.tasks.pop(1)
        draft.tasks[0].title = "展示设备准备（人工修改）"
        draft.tasks.append(AIPlannerTaskDraft(title="现场直播", deliverable="直播稳定完成并保存回放。", owner_claimable=False, collaboration_open=True))

        result = tasks_router.create_task_batch(
            TaskBatchCreate(item=TaskBatchItemIn(title=draft.item.title, deliverable=draft.item.deliverable, deadline=draft.item.deadline), tasks=draft.tasks),
            current=admin, db=db,
        )
        assert result.item.owner is not None and result.item.owner.id == admin.id
        assert len(result.tasks) == 3 and all(t.parent_id == result.item.id for t in result.tasks)
        claimable = next(t for t in result.tasks if t.title == "展示设备准备（人工修改）")
        assert claimable.owner is None and claimable.owner_claimable
        owned = next(t for t in result.tasks if t.title == "现场直播")
        assert owned.owner is not None and owned.owner.id == admin.id and not owned.owner_claimable

        rollback_title = "AI 批量事务回滚测试"
        payload = TaskBatchCreate(
            item=TaskBatchItemIn(title=rollback_title, deliverable="不应留下半套数据。", deadline=datetime(2026, 10, 13, 18, 0)),
            tasks=[AIPlannerTaskDraft(title="第一个分工", deliverable="", owner_claimable=True, collaboration_open=False)],
        )
        real_build = tasks_router._build_task
        calls = {"count": 0}
        def fail_on_child(db_arg: Session, task_payload, current):
            calls["count"] += 1
            if calls["count"] == 2:
                raise HTTPException(status_code=400, detail="forced child failure")
            return real_build(db_arg, task_payload, current)
        with patch.object(tasks_router, "_build_task", side_effect=fail_on_child):
            expect_http(400, lambda: tasks_router.create_task_batch(payload, current=admin, db=db))
        assert db.scalar(select(Task.id).where(Task.title == rollback_title)) is None

        usage = db.scalar(select(AIPlannerDailyUsage).where(AIPlannerDailyUsage.member_id == admin.id, AIPlannerDailyUsage.usage_date == planner_router._usage_date()))
        assert usage is not None and usage.input_tokens >= 120 and usage.output_tokens >= 180 and usage.total_tokens >= 300
        usage.request_count = planner_router.DAILY_REQUEST_LIMIT
        db.commit()
        expect_http(429, lambda: planner_router.generate_plan(request, current=admin, db=db, provider=FakeProvider()))

    print("AI planner tests passed")


if __name__ == "__main__":
    main()
