import io
import os
from datetime import datetime
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.datastructures import UploadFile

from app.ai_planner import PlannerGeneration, PlannerInvalidResponse, SYSTEM_PROMPT
from app.auth import get_current_member
from app.db import SessionLocal
from app.main import app
from app.knowledge import MAX_UPLOAD_BYTES
from app.models import AIPlannerDailyUsage, KnowledgeDocument, Member, Task
from app.routers import ai_planner as planner_router
from app.routers import tasks as tasks_router
from app.schemas import (
    AIPlannerDraft,
    AIPlannerItemDraft,
    AIPlannerRequest,
    AIPlannerRefineRequest,
    AIPlannerSuggestionDraft,
    AIPlannerTaskDraft,
    TaskBatchChildIn,
    TaskBatchCreate,
    TaskBatchItemIn,
)


class FakeProvider:
    def __init__(self, draft=None):
        self.calls = 0
        self.description = ""
        self.draft = draft
    def generate(self, description: str) -> PlannerGeneration:
        self.calls += 1
        self.description = description
        return PlannerGeneration(
            draft=self.draft or AIPlannerDraft(
                item=AIPlannerItemDraft(title="小学科技展", deliverable="完成现场展示并收齐活动素材。", deadline=None),
                tasks=[
                    AIPlannerTaskDraft(title="机器人与展示设备准备", deliverable="设备可正常展示并完成装车。", execution_points=["核对展示清单", "检查设备状态"], cautions=["配件一并清点"], prerequisites=["参展项目清单已确认"], owner_claimable=True, collaboration_open=False),
                    AIPlannerTaskDraft(title="现场摄影", deliverable="原图完整上传。", execution_points=["拍摄主要展示环节"], cautions=[], prerequisites=[], owner_claimable=True, collaboration_open=True),
                    AIPlannerTaskDraft(title="活动资料归档", deliverable="素材按活动归档。", execution_points=[], cautions=[], prerequisites=[], owner_claimable=True, collaboration_open=False),
                ],
                questions=["活动当天的最终结束时间是什么？"],
                suggestions=[
                    AIPlannerSuggestionDraft(
                        title="战队周边展示",
                        reason="类似科技展示曾使用少量战队周边作为展台展示，本次描述尚未提及。",
                    )
                ],
            ),
            input_tokens=120, output_tokens=180, total_tokens=300,
        )


class InvalidProvider:
    def generate(self, description: str) -> PlannerGeneration:
        raise PlannerInvalidResponse


def expect_http(expected: int, callback, *, detail: str | None = None) -> None:
    try:
        callback()
    except HTTPException as exc:
        assert exc.status_code == expected, (exc.status_code, exc.detail)
        if detail is not None:
            assert exc.detail == detail, exc.detail
        return
    raise AssertionError(f"expected HTTP {expected}")


def planner_access_for(member: Member) -> bool:
    app.dependency_overrides[get_current_member] = lambda: member
    try:
        response = TestClient(app).get("/api/ai/planner/access")
    finally:
        app.dependency_overrides.pop(get_current_member, None)
    assert response.status_code == 200, response.status_code
    return response.json()["available"]


def main() -> None:
    with SessionLocal() as db:
        assert planner_router.DAILY_REQUEST_LIMIT == 100
        admin = db.scalar(select(Member).where(Member.email == "admin@example.com"))
        manager = db.scalar(select(Member).where(Member.email == "manager@example.com"))
        member = db.scalar(select(Member).where(Member.role == "member", Member.status == "active").order_by(Member.id).limit(1))
        assert admin is not None and manager is not None and member is not None
        os.environ.update({
            "AI_PLANNER_ENABLED": "true",
            "AI_API_KEY": "ci-placeholder",
            "AI_MODEL": "ci-placeholder",
        })

        assert "questions 的优先级最低" in SYSTEM_PROMPT
        assert "title、deliverable、execution_points 或 prerequisites" in SYSTEM_PROMPT
        assert "该 question 必须删除" in SYSTEM_PROMPT
        assert "没有任何已有或可合理生成的团队 task 能够解决该未知" in SYSTEM_PROMPT
        assert "即使负责人现在直接回答会更方便" in SYSTEM_PROMPT
        assert "不得因为直播通常需要网络而生成或询问网络条件" in SYSTEM_PROMPT
        assert "这条排除规则也覆盖 deliverable、execution_points、cautions、prerequisites、questions 和 suggestions" in SYSTEM_PROMPT

        anonymous_upload = TestClient(app).post(
            "/api/ai/planner/extract",
            files={"file": ("event.txt", b"A confirmed event date is October 12.")},
        )
        assert anonymous_upload.status_code == 401

        manager_upload = UploadFile(filename="event.txt", file=io.BytesIO(b"event details"))
        expect_http(
            403,
            lambda: planner_router.extract_planner_material(file=manager_upload, current=manager),
        )
        assert manager_upload.file.closed

        documents_before = db.scalar(select(func.count(KnowledgeDocument.id))) or 0
        planner_upload = UploadFile(
            filename="../../current-event.txt",
            file=io.BytesIO("本次活动时间为 10 月 12 日。".encode()),
        )
        extracted = planner_router.extract_planner_material(file=planner_upload, current=admin)
        assert extracted.filename == "current-event.txt"
        assert extracted.parse_status == "ready" and "10 月 12 日" in extracted.extracted_text
        assert planner_upload.file.closed
        assert (db.scalar(select(func.count(KnowledgeDocument.id))) or 0) == documents_before

        unsupported_upload = UploadFile(filename="event.zip", file=io.BytesIO(b"archive"))
        expect_http(415, lambda: planner_router.extract_planner_material(file=unsupported_upload, current=admin))
        assert unsupported_upload.file.closed

        oversized_upload = UploadFile(
            filename="oversized.txt",
            file=io.BytesIO(b"x" * (MAX_UPLOAD_BYTES + 1)),
        )
        expect_http(413, lambda: planner_router.extract_planner_material(file=oversized_upload, current=admin))
        assert oversized_upload.file.closed

        broken_upload = UploadFile(filename="broken.pdf", file=io.BytesIO(b"not a PDF"))
        failed_extraction = planner_router.extract_planner_material(file=broken_upload, current=admin)
        assert failed_extraction.parse_status == "failed"
        assert failed_extraction.error and "解析" in failed_extraction.error
        assert broken_upload.file.closed

        extra_admin = Member(name="测试管理员", email="planner-extra-admin@example.com", password_hash=None, role="admin", status="active")
        db.add(extra_admin)
        db.commit()

        request = AIPlannerRequest(description="准备一次校园科技展示，需要展示、摄影和资料整理。")
        inactive_admin = Member(name="停用管理员", email="inactive-ai-admin@example.com", password_hash=None, role="admin", status="disabled")
        assert planner_access_for(admin)
        assert planner_access_for(extra_admin)
        assert not planner_access_for(manager)
        assert not planner_access_for(member)
        assert not planner_access_for(inactive_admin)
        expect_http(403, lambda: planner_router.generate_plan(request, current=manager, db=db, provider=FakeProvider()))
        expect_http(403, lambda: planner_router.generate_plan(request, current=member, db=db, provider=FakeProvider()))
        expect_http(403, lambda: planner_router.generate_plan(request, current=inactive_admin, db=db, provider=FakeProvider()))
        extra_admin_generate = FakeProvider()
        planner_router.generate_plan(request, current=extra_admin, db=db, provider=extra_admin_generate)
        assert extra_admin_generate.calls == 1

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
        result = planner_router.generate_plan(request, current=admin, db=db, provider=provider)
        after = db.scalar(select(func.count(Task.id))) or 0
        assert provider.calls == 1 and before == after
        draft = result.draft
        assert draft.item.deliverable == ""
        assert not hasattr(draft.tasks[0], "owner_id")
        assert draft.tasks[0].execution_points and draft.tasks[0].cautions and draft.tasks[0].prerequisites
        assert [suggestion.title for suggestion in draft.suggestions] == ["战队周边展示"]
        rejected_live_draft = AIPlannerDraft(
            item=AIPlannerItemDraft(title="机器人科技展", deliverable="模型生成的 root 总标准。", deadline=None),
            tasks=[
                AIPlannerTaskDraft(
                    title="现场展示",
                    deliverable="展示设备可运行，直播画面稳定。",
                    execution_points=["核对展示清单", "确认网络条件并测试在线演示"],
                    cautions=["网络不可用时准备直播方案"],
                    prerequisites=["直播网络已确认"],
                    owner_claimable=True,
                    collaboration_open=False,
                ),
                AIPlannerTaskDraft(
                    title="确认直播与网络条件",
                    deliverable="直播网络可用。",
                    execution_points=[],
                    cautions=[],
                    prerequisites=[],
                    owner_claimable=True,
                    collaboration_open=False,
                ),
            ],
            questions=["是否需要直播？", "活动时间是否已确认？"],
            suggestions=[
                AIPlannerSuggestionDraft(title="现场直播", reason="团队指南将直播作为可选方式。"),
                AIPlannerSuggestionDraft(title="活动宣传安排", reason="团队指南将宣传作为可选模块。"),
            ],
        )
        rejected_live_provider = FakeProvider(draft=rejected_live_draft)
        rejected_live_result = planner_router.generate_plan(
            AIPlannerRequest(description="10 月 12 日去小学参加机器人科技展，不需要直播。"),
            current=admin,
            db=db,
            provider=rejected_live_provider,
        )
        assert rejected_live_provider.calls == 1
        assert [task.title for task in rejected_live_result.draft.tasks] == ["现场展示"]
        assert rejected_live_result.draft.tasks[0].deliverable == "展示设备可运行"
        assert rejected_live_result.draft.tasks[0].execution_points == ["核对展示清单"]
        assert rejected_live_result.draft.tasks[0].cautions == []
        assert rejected_live_result.draft.tasks[0].prerequisites == []
        assert rejected_live_result.draft.questions == ["活动时间是否已确认？"]
        assert [item.title for item in rejected_live_result.draft.suggestions] == ["活动宣传安排"]
        remaining_planner_text = " ".join(
            [
                *rejected_live_result.draft.questions,
                *[suggestion.title + suggestion.reason for suggestion in rejected_live_result.draft.suggestions],
                *[
                    text
                    for task in rejected_live_result.draft.tasks
                    for text in [task.title, task.deliverable, *task.execution_points, *task.cautions, *task.prerequisites]
                ],
            ]
        )
        assert not any(term in remaining_planner_text for term in ("直播", "网络", "联网", "在线演示"))
        assert rejected_live_result.draft.item.deliverable == ""
        empty_root_batch = tasks_router.create_task_batch(
            TaskBatchCreate(
                item=TaskBatchItemIn(title="空 root 完成标准兼容测试", deliverable="", deadline=datetime(2026, 10, 12, 18, 0)),
                tasks=[TaskBatchChildIn(title="兼容 child", deliverable="", owner_claimable=True, collaboration_open=False)],
            ),
            current=admin,
            db=db,
        )
        for task_id in [task.id for task in empty_root_batch.tasks] + [empty_root_batch.item.id]:
            db.delete(db.get(Task, task_id))
        db.commit()
        denied_refine = AIPlannerRefineRequest(
            description=request.description,
            draft=draft,
            instruction="检查遗漏",
        )
        expect_http(403, lambda: planner_router.refine_plan(denied_refine, current=manager, db=db, provider=FakeProvider()))
        expect_http(403, lambda: planner_router.refine_plan(denied_refine, current=member, db=db, provider=FakeProvider()))
        expect_http(403, lambda: planner_router.refine_plan(denied_refine, current=inactive_admin, db=db, provider=FakeProvider()))
        extra_admin_refine = FakeProvider()
        planner_router.refine_plan(denied_refine, current=extra_admin, db=db, provider=extra_admin_refine)
        assert extra_admin_refine.calls == 1

        attachment_facts = "文件《科技展通知.txt》：\n本次活动日期为 10 月 12 日，地点为力旺实验小学。"
        attachment_request = AIPlannerRequest(
            description="准备一次校园科技展示，请整理能先安排的工作。",
            current_event_context=attachment_facts,
        )
        attachment_provider = FakeProvider()
        planner_router.generate_plan(
            attachment_request,
            current=admin,
            db=db,
            provider=attachment_provider,
        )
        assert attachment_provider.calls == 1
        assert "【本次事项资料】" in attachment_provider.description
        assert "科技展通知.txt" in attachment_provider.description
        assert "10 月 12 日" in attachment_provider.description

        original_dump = result.draft.model_dump(mode="json")
        scoped_output = AIPlannerDraft(
            item=AIPlannerItemDraft(title="模型不应覆盖事项标题", deliverable="忽略", deadline=None),
            tasks=[AIPlannerTaskDraft(
                title="更适合新人执行的摄影任务",
                deliverable="活动关键环节影像均已采集并上传。",
                execution_points=["提前确认设备可用", "按活动流程补齐关键环节"],
                cautions=["保留设备电量余量"],
                prerequisites=["获取活动流程"],
                owner_claimable=False,
                collaboration_open=False,
            )],
            questions=["不应覆盖原问题"],
            suggestions=[
                AIPlannerSuggestionDraft(title="不应覆盖原建议", reason="单卡调整输出中的建议应被后端忽略。")
            ],
        )
        scoped_provider = FakeProvider(draft=scoped_output)
        scoped = planner_router.refine_plan(
            AIPlannerRefineRequest(
                description=request.description,
                draft=result.draft,
                instruction="让新人拿到后更容易执行",
                scope_task_index=1,
            ),
            current=admin,
            db=db,
            provider=scoped_provider,
        )
        assert scoped_provider.calls == 1
        assert "只调整第 2 张任务卡" in scoped_provider.description
        assert "1. 机器人与展示设备准备\n2. 现场摄影\n3. 活动资料归档" in scoped_provider.description
        assert "编号不是数据库 ID" in scoped_provider.description
        assert "每次 refine 都必须按收到的最新 draft 重新编号" in scoped_provider.description
        assert scoped.draft.item.title == original_dump["item"]["title"]
        assert scoped.draft.questions == result.draft.questions
        assert scoped.draft.suggestions == result.draft.suggestions
        assert scoped.draft.tasks[0].model_dump() == result.draft.tasks[0].model_dump()
        assert scoped.draft.tasks[2].model_dump() == result.draft.tasks[2].model_dump()
        assert scoped.draft.tasks[1].title == "更适合新人执行的摄影任务"
        assert scoped.draft.tasks[1].owner_claimable is result.draft.tasks[1].owner_claimable
        assert scoped.draft.tasks[1].collaboration_open is result.draft.tasks[1].collaboration_open

        global_output = AIPlannerDraft(
            item=AIPlannerItemDraft(title="精简后的科技展", deliverable="方案可执行。", deadline=None),
            tasks=[AIPlannerTaskDraft(
                title="整合后的展示执行",
                deliverable="展示环节已完成。",
                execution_points=["准备并检查展示设备"],
                cautions=[], prerequisites=[], owner_claimable=True, collaboration_open=False,
            )],
            questions=[],
            suggestions=[
                AIPlannerSuggestionDraft(title="新提醒", reason="全局调整允许根据当前知识重新生成可能遗漏。")
            ],
        )
        global_provider = FakeProvider(draft=global_output)
        global_result = planner_router.refine_plan(
            AIPlannerRefineRequest(
                description=request.description,
                draft=result.draft,
                instruction="把方案精简成一个完整的展示执行任务",
            ),
            current=admin,
            db=db,
            provider=global_provider,
        )
        assert global_provider.calls == 1
        assert "全局调整" in global_provider.description
        assert global_result.draft.item.title == "精简后的科技展"
        assert global_result.draft.item.deliverable == ""
        assert len(global_result.draft.tasks) == 1 and global_result.draft.questions == []
        assert [suggestion.title for suggestion in global_result.draft.suggestions] == ["新提醒"]

        reordered_draft = result.draft.model_copy(deep=True)
        reordered_draft.tasks = list(reversed(reordered_draft.tasks))
        reordered_provider = FakeProvider(draft=global_output)
        planner_router.refine_plan(
            AIPlannerRefineRequest(
                description=request.description,
                draft=reordered_draft,
                instruction="移除第 1 个任务",
            ),
            current=admin,
            db=db,
            provider=reordered_provider,
        )
        assert reordered_provider.calls == 1
        assert "1. 活动资料归档\n2. 现场摄影\n3. 机器人与展示设备准备" in reordered_provider.description
        assert "任务编号】\n1." in reordered_provider.description

        join_output = AIPlannerDraft(
            item=result.draft.item.model_copy(deep=True),
            tasks=[
                AIPlannerTaskDraft(
                    title="机器人与展示设备准备",
                    deliverable="设备和用于展台展示的战队周边准备完成，可按清单出发。",
                    execution_points=["核对展示设备", "准备少量战队周边用于展台展示"],
                    cautions=["周边仅用于展示，不扩展到其他用途"],
                    prerequisites=[],
                    owner_claimable=True,
                    collaboration_open=False,
                ),
                result.draft.tasks[1].model_copy(deep=True),
                result.draft.tasks[2].model_copy(deep=True),
            ],
            questions=[],
            suggestions=[],
        )
        join_provider = FakeProvider(draft=join_output)
        join_instruction = (
            "负责人已确认将“战队周边展示”纳入本次事项。请将其合理融合进当前方案，"
            "按照真实责任边界决定是新增 task 还是加入现有 task 的 execution_points / cautions / prerequisites。"
            "不要再把它保留为 suggestion。只纳入这一已确认子意图，不要扩展到未确认的相邻用途。"
        )
        joined = planner_router.refine_plan(
            AIPlannerRefineRequest(
                description=request.description,
                draft=result.draft,
                instruction=join_instruction,
            ),
            current=admin,
            db=db,
            provider=join_provider,
        )
        assert join_provider.calls == 1
        assert join_instruction in join_provider.description
        assert joined.draft.suggestions == []
        joined_text = joined.draft.model_dump_json()
        assert "战队周边" in joined_text
        for forbidden in ("周边发放", "周边礼赠", "周边采购", "周边宣传"):
            assert forbidden not in joined_text

        expect_http(502, lambda: planner_router.generate_plan(request, current=admin, db=db, provider=InvalidProvider()))

        draft.item.title = "小学科技展（人工确认）"
        draft.item.deliverable = "完成展示，并在当天收齐现场素材。"
        draft.item.deadline = datetime(2026, 10, 12, 18, 0)
        draft.tasks.pop(1)
        draft.tasks[0].title = "展示设备准备（人工修改）"
        draft.tasks.append(AIPlannerTaskDraft(title="现场直播", deliverable="直播稳定完成并保存回放。", execution_points=["确认直播链路"], cautions=[], prerequisites=[], owner_claimable=False, collaboration_open=True))

        assert [suggestion.title for suggestion in draft.suggestions] == ["战队周边展示"]
        try:
            TaskBatchCreate.model_validate({
                "item": {
                    "title": draft.item.title,
                    "deliverable": draft.item.deliverable,
                    "deadline": draft.item.deadline,
                },
                "tasks": [TaskBatchChildIn.model_validate(task.model_dump()).model_dump() for task in draft.tasks],
                "suggestions": [suggestion.model_dump() for suggestion in draft.suggestions],
            })
        except ValidationError:
            pass
        else:
            raise AssertionError("batch create must reject planner-only suggestions")

        result = tasks_router.create_task_batch(
            TaskBatchCreate(
                item=TaskBatchItemIn(
                    title=draft.item.title,
                    deliverable=draft.item.deliverable,
                    deadline=draft.item.deadline,
                ),
                tasks=[TaskBatchChildIn.model_validate(task.model_dump()) for task in draft.tasks],
            ),
            current=admin, db=db,
        )
        assert result.item.owner is not None and result.item.owner.id == admin.id
        assert len(result.tasks) == 3 and all(t.parent_id == result.item.id for t in result.tasks)
        assert all(task.title != "战队周边展示" for task in result.tasks)
        claimable = next(t for t in result.tasks if t.title == "展示设备准备（人工修改）")
        assert claimable.owner is None and claimable.owner_claimable
        owned = next(t for t in result.tasks if t.title == "现场直播")
        assert owned.owner is not None and owned.owner.id == admin.id and not owned.owner_claimable
        assert claimable.execution_points == ["核对展示清单", "检查设备状态"]
        assert claimable.cautions == ["配件一并清点"]
        assert claimable.prerequisites == ["参展项目清单已确认"]
        db.expire_all()
        persisted_claimable = db.get(Task, claimable.id)
        assert persisted_claimable.execution_points == ["核对展示清单", "检查设备状态"]
        assert persisted_claimable.cautions == ["配件一并清点"]
        assert persisted_claimable.prerequisites == ["参展项目清单已确认"]

        rollback_title = "AI 批量事务回滚测试"
        payload = TaskBatchCreate(
            item=TaskBatchItemIn(title=rollback_title, deliverable="不应留下半套数据。", deadline=datetime(2026, 10, 13, 18, 0)),
            tasks=[
                TaskBatchChildIn(
                    title="第一个分工",
                    deliverable="",
                    owner_claimable=True,
                    collaboration_open=False,
                )
            ],
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
        expected_limit_message = "今日 AI 使用次数已达上限，请稍后再试。"
        denied_generate_provider = FakeProvider()
        expect_http(
            429,
            lambda: planner_router.generate_plan(
                request,
                current=admin,
                db=db,
                provider=denied_generate_provider,
            ),
            detail=expected_limit_message,
        )
        assert denied_generate_provider.calls == 0
        denied_refine_provider = FakeProvider()
        expect_http(
            429,
            lambda: planner_router.refine_plan(
                denied_refine,
                current=admin,
                db=db,
                provider=denied_refine_provider,
            ),
            detail=expected_limit_message,
        )
        assert denied_refine_provider.calls == 0

        for usage_row in db.scalars(
            select(AIPlannerDailyUsage).where(AIPlannerDailyUsage.member_id == extra_admin.id)
        ).all():
            db.delete(usage_row)
        db.delete(extra_admin)
        db.commit()

    print("AI planner tests passed")


if __name__ == "__main__":
    main()
