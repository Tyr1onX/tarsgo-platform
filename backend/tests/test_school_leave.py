"""MySQL-backed School Leave v1 workflow and privacy coverage."""

from __future__ import annotations

import io
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from docx import Document
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.auth import get_current_member
from app.db import SessionLocal, get_db
from app.main import app
from app.models import Member, SchoolLeaveRequest, SchoolLeaveRun
from app.school_leave import collect_pending_school_leave


TEST_EMAILS = (
    "leave-admin@example.com",
    "leave-manager@example.com",
    "leave-a@example.com",
    "leave-b@example.com",
    "leave-c@example.com",
    "leave-missing@example.com",
)


def set_actor(member: Member) -> None:
    app.dependency_overrides[get_current_member] = lambda: member


def request_payload(start: str, end: str) -> dict[str, str]:
    return {"start_at": start, "end_at": end}


def docx_text(content: bytes) -> str:
    document = Document(io.BytesIO(content))
    text_parts = [paragraph.text for paragraph in document.paragraphs]
    for table in document.tables:
        for row in table.rows:
            text_parts.extend(cell.text for cell in row.cells)
    return "\n".join(text_parts)


def main() -> None:
    previous_phone = os.environ.get("LEAVE_CONTACT_PHONE")
    previous_cutoff = os.environ.get("LEAVE_DAILY_CUTOFF")
    previous_overrides = dict(app.dependency_overrides)

    with SessionLocal() as db:
        existing_ids = list(db.scalars(select(Member.id).where(Member.email.in_(TEST_EMAILS))))
        if existing_ids:
            run_ids = list(
                db.scalars(
                    select(SchoolLeaveRequest.run_id)
                    .where(
                        SchoolLeaveRequest.member_id.in_(existing_ids),
                        SchoolLeaveRequest.run_id.is_not(None),
                    )
                    .distinct()
                )
            )
            db.execute(delete(SchoolLeaveRequest).where(SchoolLeaveRequest.member_id.in_(existing_ids)))
            if run_ids:
                db.execute(delete(SchoolLeaveRun).where(SchoolLeaveRun.id.in_(run_ids)))
            db.execute(delete(SchoolLeaveRun).where(SchoolLeaveRun.created_by.in_(existing_ids)))
            db.execute(delete(Member).where(Member.id.in_(existing_ids)))
            db.commit()

        admin = Member(
            name="测试管理员",
            email=TEST_EMAILS[0],
            student_id="TEST900001",
            role="admin",
            status="active",
        )
        manager = Member(
            name="测试任务管理员",
            email=TEST_EMAILS[1],
            student_id="TEST900002",
            role="manager",
            status="active",
        )
        member_a = Member(
            name="测试甲",
            email=TEST_EMAILS[2],
            student_id="TEST100001",
            role="member",
            status="active",
        )
        member_b = Member(
            name="测试乙",
            email=TEST_EMAILS[3],
            student_id="TEST100002",
            role="member",
            status="active",
        )
        member_c = Member(
            name="测试丙",
            email=TEST_EMAILS[4],
            student_id="TEST100003",
            role="member",
            status="active",
        )
        missing_id = Member(
            name="测试未填学号",
            email=TEST_EMAILS[5],
            student_id=None,
            role="member",
            status="active",
        )
        db.add_all([admin, manager, member_a, member_b, member_c, missing_id])
        db.commit()
        for member in (admin, manager, member_a, member_b, member_c, missing_id):
            db.refresh(member)

        def override_database():
            yield db

        app.dependency_overrides[get_db] = override_database
        client = TestClient(app)

        try:
            # 1. A student id is mandatory for school-leave submission.
            set_actor(missing_id)
            response = client.post(
                "/api/school-leave/requests",
                json=request_payload("2026-10-08T13:00:00", "2026-10-08T17:00:00"),
            )
            assert response.status_code == 409, response.text
            assert response.json()["detail"] == "请先完善学号，生成学校请假材料时需要使用。"

            # Task member summaries must not start exposing student ids.
            set_actor(manager)
            task_assignees = client.get("/api/tasks/assignees")
            assert task_assignees.status_code == 200, task_assignees.text
            assert all("student_id" not in row for row in task_assignees.json())

            # 2/3. A member can update/withdraw only their own pending request.
            set_actor(member_a)
            first = client.post(
                "/api/school-leave/requests",
                json=request_payload("2026-10-08T13:00:00", "2026-10-08T17:00:00"),
            )
            assert first.status_code == 201, first.text
            first_id = first.json()["id"]
            assert first.json()["student_id_snapshot"] == "TEST100001"

            updated = client.patch(
                f"/api/school-leave/requests/{first_id}",
                json=request_payload("2026-10-08T13:05:00", "2026-10-08T17:00:00"),
            )
            assert updated.status_code == 200, updated.text
            assert updated.json()["start_at"].startswith("2026-10-08T13:05")

            set_actor(member_b)
            forbidden_update = client.patch(
                f"/api/school-leave/requests/{first_id}",
                json=request_payload("2026-10-08T13:10:00", "2026-10-08T17:00:00"),
            )
            assert forbidden_update.status_code == 404

            set_actor(member_a)
            withdrawn = client.post(f"/api/school-leave/requests/{first_id}/withdraw")
            assert withdrawn.status_code == 200
            assert withdrawn.json()["status"] == "withdrawn"

            # Prepare one exact shared group plus one different group.
            a_response = client.post(
                "/api/school-leave/requests",
                json=request_payload("2026-10-08T13:00:00", "2026-10-08T17:00:00"),
            )
            assert a_response.status_code == 201
            a_request_id = a_response.json()["id"]

            set_actor(member_b)
            b_response = client.post(
                "/api/school-leave/requests",
                json=request_payload("2026-10-08T13:00:00", "2026-10-08T17:00:00"),
            )
            assert b_response.status_code == 201
            b_request_id = b_response.json()["id"]

            set_actor(member_c)
            c_response = client.post(
                "/api/school-leave/requests",
                json=request_payload("2026-10-08T15:00:00", "2026-10-08T17:00:00"),
            )
            assert c_response.status_code == 201
            c_request_id = c_response.json()["id"]

            # 11. manager/member never gain school-leave administration permission.
            set_actor(manager)
            assert client.get("/api/school-leave/admin/runs").status_code == 403
            assert client.post("/api/school-leave/admin/runs/collect").status_code == 403
            set_actor(member_a)
            assert client.get("/api/school-leave/admin/requests").status_code == 403

            # 5/6. Collection groups only exact equal start/end times.
            set_actor(admin)
            collected = client.post("/api/school-leave/admin/runs/collect")
            assert collected.status_code == 200, collected.text
            run_one = collected.json()
            assert run_one is not None
            run_one_id = run_one["id"]
            assert [(group["time_text"], group["count"]) for group in run_one["groups"]] == [
                ("2026 年 10 月 8 日 13:00 至 17:00", 2),
                ("2026 年 10 月 8 日 15:00 至 17:00", 1),
            ]

            # 4. Included requests are frozen for members.
            set_actor(member_a)
            included_update = client.patch(
                f"/api/school-leave/requests/{a_request_id}",
                json=request_payload("2026-10-08T13:05:00", "2026-10-08T17:00:00"),
            )
            assert included_update.status_code == 409

            # 17. Profile changes never mutate frozen snapshots.
            member_a.student_id = "TEST199999"
            db.commit()
            set_actor(admin)
            run_one_fresh = next(
                run for run in client.get("/api/school-leave/admin/runs").json()
                if run["id"] == run_one_id
            )
            shared_group_ids = [person["student_id"] for person in run_one_fresh["groups"][0]["members"]]
            assert "TEST100001" in shared_group_ids
            assert "TEST199999" not in shared_group_ids

            # 8/9. Later submissions stay pending; cancelling a ready run releases included rows.
            set_actor(member_a)
            later = client.post(
                "/api/school-leave/requests",
                json=request_payload("2026-10-08T18:00:00", "2026-10-08T19:00:00"),
            )
            assert later.status_code == 201
            later_id = later.json()["id"]
            assert later.json()["status"] == "pending"
            assert later.json()["run_id"] is None

            set_actor(admin)
            cancelled = client.post(f"/api/school-leave/admin/runs/{run_one_id}/cancel")
            assert cancelled.status_code == 200, cancelled.text
            assert cancelled.json()["status"] == "cancelled"
            db.expire_all()
            for request_id in (a_request_id, b_request_id, c_request_id):
                request = db.get(SchoolLeaveRequest, request_id)
                assert request and request.status == "pending" and request.run_id is None

            # Re-collect the released requests plus the later supplement.
            recollected = client.post("/api/school-leave/admin/runs/collect")
            assert recollected.status_code == 200, recollected.text
            run_two = recollected.json()
            run_two_id = run_two["id"]
            assert run_two["request_count"] == 4
            assert [group["count"] for group in run_two["groups"]] == [2, 1, 1]

            # Ready reason can change and is reflected deterministically in generated files.
            reason = "参加虚构机器人战队校内创新实践活动"
            changed_reason = client.patch(
                f"/api/school-leave/admin/runs/{run_two_id}/reason",
                json={"reason": reason},
            )
            assert changed_reason.status_code == 200
            assert changed_reason.json()["reason"] == reason

            # 14. Missing private phone configuration safely blocks documents.
            os.environ.pop("LEAVE_CONTACT_PHONE", None)
            missing_phone = client.get(
                f"/api/school-leave/admin/runs/{run_two_id}/documents/0"
            )
            assert missing_phone.status_code == 503
            assert "LEAVE_CONTACT_PHONE" in missing_phone.json()["detail"]

            # 12/13. Admin can generate deterministic DOCX with snapshots/time/body.
            os.environ["LEAVE_CONTACT_PHONE"] = "000-0000-0000"
            doc_response = client.get(
                f"/api/school-leave/admin/runs/{run_two_id}/documents/0"
            )
            assert doc_response.status_code == 200, doc_response.text
            rendered = docx_text(doc_response.content)
            assert "请假条" in rendered
            assert reason in rendered
            assert "2026 年 10 月 8 日 13:00 至 17:00" in rendered
            assert "测试甲" in rendered and "TEST100001" in rendered
            assert "测试乙" in rendered and "TEST100002" in rendered
            assert "TEST199999" not in rendered
            assert "联系电话：000-0000-0000" in rendered

            # 15. ZIP contains exactly one DOCX per exact time group.
            zip_response = client.get(
                f"/api/school-leave/admin/runs/{run_two_id}/documents.zip"
            )
            assert zip_response.status_code == 200, zip_response.text
            import zipfile

            with zipfile.ZipFile(io.BytesIO(zip_response.content)) as archive:
                names = archive.namelist()
                assert len(names) == 3
                assert all(name.endswith(".docx") for name in names)
                assert len(set(names)) == 3

            # 16/10. Marking sent records actor/time; a sent run cannot be changed/cancelled.
            marked = client.post(f"/api/school-leave/admin/runs/{run_two_id}/sent")
            assert marked.status_code == 200, marked.text
            assert marked.json()["status"] == "sent"
            assert marked.json()["sent_by"]["id"] == admin.id
            assert marked.json()["sent_at"]
            assert client.post(f"/api/school-leave/admin/runs/{run_two_id}/cancel").status_code == 409
            assert client.patch(
                f"/api/school-leave/admin/runs/{run_two_id}/reason",
                json={"reason": "不应允许修改"},
            ).status_code == 409

            # A later request forms a fresh supplementary run and never mutates the sent one.
            set_actor(member_b)
            supplement = client.post(
                "/api/school-leave/requests",
                json=request_payload("2026-10-08T20:00:00", "2026-10-08T21:00:00"),
            )
            assert supplement.status_code == 201
            supplement_id = supplement.json()["id"]

            set_actor(admin)
            supplement_run = client.post("/api/school-leave/admin/runs/collect")
            assert supplement_run.status_code == 200
            run_three = supplement_run.json()
            assert run_three["id"] != run_two_id
            assert run_three["request_count"] == 1
            db.expire_all()
            sent_request_ids = {
                request.id
                for request in db.scalars(
                    select(SchoolLeaveRequest).where(SchoolLeaveRequest.run_id == run_two_id)
                )
            }
            assert supplement_id not in sent_request_ids
            assert db.get(SchoolLeaveRun, run_two_id).status == "sent"

            # 18. No pending requests is an idempotent safe no-op.
            assert collect_pending_school_leave(db, created_by=None) is None

            # 7. Two simultaneous collectors can include a pending request only once.
            set_actor(member_c)
            concurrency_request = client.post(
                "/api/school-leave/requests",
                json=request_payload("2026-10-09T08:00:00", "2026-10-09T09:00:00"),
            )
            assert concurrency_request.status_code == 201
            concurrency_request_id = concurrency_request.json()["id"]
            db.commit()

            def collect_worker() -> int | None:
                with SessionLocal() as worker_db:
                    run = collect_pending_school_leave(worker_db, created_by=None)
                    return run.id if run else None

            with ThreadPoolExecutor(max_workers=2) as executor:
                run_ids = list(executor.map(lambda _: collect_worker(), range(2)))

            created_run_ids = [run_id for run_id in run_ids if run_id is not None]
            assert len(created_run_ids) == 1, run_ids
            db.expire_all()
            concurrency_row = db.get(SchoolLeaveRequest, concurrency_request_id)
            assert concurrency_row and concurrency_row.status == "included"
            assert concurrency_row.run_id == created_run_ids[0]

            # Cutoff parsing is configuration-only and visible to admins without exposing phone.
            os.environ["LEAVE_DAILY_CUTOFF"] = "11:30"
            set_actor(admin)
            config = client.get("/api/school-leave/admin/config")
            assert config.status_code == 200
            assert config.json() == {
                "daily_cutoff": "11:30",
                "contact_phone_configured": True,
            }

            # Sanity-check exact request statuses used throughout the workflow.
            db.expire_all()
            assert db.get(SchoolLeaveRequest, first_id).status == "withdrawn"
            assert db.get(SchoolLeaveRequest, later_id).run_id == run_two_id

        finally:
            app.dependency_overrides.clear()
            app.dependency_overrides.update(previous_overrides)
            test_member_ids = [
                admin.id,
                manager.id,
                member_a.id,
                member_b.id,
                member_c.id,
                missing_id.id,
            ]
            run_ids = list(
                db.scalars(
                    select(SchoolLeaveRequest.run_id)
                    .where(
                        SchoolLeaveRequest.member_id.in_(test_member_ids),
                        SchoolLeaveRequest.run_id.is_not(None),
                    )
                    .distinct()
                )
            )
            db.execute(delete(SchoolLeaveRequest).where(SchoolLeaveRequest.member_id.in_(test_member_ids)))
            if run_ids:
                db.execute(delete(SchoolLeaveRun).where(SchoolLeaveRun.id.in_(run_ids)))
            db.execute(delete(SchoolLeaveRun).where(SchoolLeaveRun.created_by.in_(test_member_ids)))
            db.execute(delete(Member).where(Member.id.in_(test_member_ids)))
            db.commit()

    if previous_phone is None:
        os.environ.pop("LEAVE_CONTACT_PHONE", None)
    else:
        os.environ["LEAVE_CONTACT_PHONE"] = previous_phone
    if previous_cutoff is None:
        os.environ.pop("LEAVE_DAILY_CUTOFF", None)
    else:
        os.environ["LEAVE_DAILY_CUTOFF"] = previous_cutoff

    print("School leave tests passed")


if __name__ == "__main__":
    main()
