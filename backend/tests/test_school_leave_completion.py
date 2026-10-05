"""MySQL-backed coverage for the School Leave completion loop and private result files."""

from __future__ import annotations

import os
import tempfile
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.auth import get_current_member
from app.db import SessionLocal, get_db
from app.main import app
from app.models import Member, SchoolLeaveGroupResult, SchoolLeaveRequest, SchoolLeaveRun
from app.school_leave import (
    SCHOOL_LEAVE_RESULT_MAX_BYTES,
    cleanup_expired_school_leave_results,
    school_leave_now,
    school_leave_result_file_path,
)


def main() -> None:
    token = uuid4().hex
    emails = {
        "admin": f"leave-loop-admin-{token}@example.invalid",
        "a": f"leave-loop-a-{token}@example.invalid",
        "b": f"leave-loop-b-{token}@example.invalid",
        "c": f"leave-loop-c-{token}@example.invalid",
        "d": f"leave-loop-d-{token}@example.invalid",
    }
    previous_phone = os.environ.get("LEAVE_CONTACT_PHONE")
    previous_storage = os.environ.get("SCHOOL_LEAVE_RESULT_STORAGE_DIR")
    previous_overrides = dict(app.dependency_overrides)
    storage = tempfile.TemporaryDirectory()

    os.environ["SCHOOL_LEAVE_RESULT_STORAGE_DIR"] = storage.name
    created_member_ids: list[int] = []
    created_run_ids: list[int] = []

    try:
        with SessionLocal() as db:
            members = {
                "admin": Member(
                    name="闭环管理员",
                    email=emails["admin"],
                    student_id=f"ADMIN-{token[:8]}",
                    role="admin",
                    status="active",
                ),
                "a": Member(
                    name="闭环甲",
                    email=emails["a"],
                    student_id=f"A-{token[:8]}",
                    role="member",
                    status="active",
                ),
                "b": Member(
                    name="闭环乙",
                    email=emails["b"],
                    student_id=f"B-{token[:8]}",
                    role="member",
                    status="active",
                ),
                "c": Member(
                    name="闭环丙",
                    email=emails["c"],
                    student_id=f"C-{token[:8]}",
                    role="member",
                    status="active",
                ),
                "d": Member(
                    name="闭环无关成员",
                    email=emails["d"],
                    student_id=f"D-{token[:8]}",
                    role="member",
                    status="active",
                ),
            }
            db.add_all(members.values())
            db.commit()
            for member in members.values():
                db.refresh(member)
                created_member_ids.append(member.id)

            def override_database():
                yield db

            def set_actor(key: str) -> None:
                app.dependency_overrides[get_current_member] = lambda: members[key]

            app.dependency_overrides[get_db] = override_database
            client = TestClient(app)

            def submit(key: str, start: str, end: str) -> int:
                set_actor(key)
                response = client.post(
                    "/api/school-leave/requests",
                    json={"start_at": start, "end_at": end},
                )
                assert response.status_code == 201, response.text
                return response.json()["id"]

            # One frozen run has two deterministic exact-time groups.
            a_request_id = submit("a", "2026-10-10T13:00:00", "2026-10-10T17:00:00")
            b_request_id = submit("b", "2026-10-10T13:00:00", "2026-10-10T17:00:00")
            c_request_id = submit("c", "2026-10-10T15:00:00", "2026-10-10T17:00:00")

            set_actor("admin")
            collected = client.post("/api/school-leave/admin/runs/collect")
            assert collected.status_code == 200, collected.text
            run_id = collected.json()["id"]
            created_run_ids.append(run_id)
            assert [group["count"] for group in collected.json()["groups"]] == [2, 1]

            summary = client.get("/api/school-leave/admin/summary")
            assert summary.status_code == 200
            assert summary.json() == {
                "ready_count": 1,
                "awaiting_return_count": 0,
                "todo_count": 1,
            }
            set_actor("a")
            assert client.get("/api/school-leave/admin/summary").status_code == 403

            # Member cannot download the original Word or upload a returned result.
            assert client.get(f"/api/school-leave/admin/runs/{run_id}/document").status_code == 403
            forbidden_upload = client.post(
                f"/api/school-leave/admin/runs/{run_id}/groups/0/result",
                files={"file": ("stamp.jpg", b"member", "image/jpeg")},
            )
            assert forbidden_upload.status_code == 403

            # Generation failure never advances ready state.
            set_actor("admin")
            os.environ.pop("LEAVE_CONTACT_PHONE", None)
            failed_document = client.get(f"/api/school-leave/admin/runs/{run_id}/document")
            assert failed_document.status_code == 503
            db.expire_all()
            assert db.get(SchoolLeaveRun, run_id).status == "ready"
            assert client.delete(f"/api/school-leave/admin/runs/{run_id}").status_code == 409

            # First successful download atomically starts the real-world processing loop.
            os.environ["LEAVE_CONTACT_PHONE"] = "000-0000-0000"
            downloaded = client.get(f"/api/school-leave/admin/runs/{run_id}/document")
            assert downloaded.status_code == 200, downloaded.text
            db.expire_all()
            run = db.get(SchoolLeaveRun, run_id)
            assert run is not None
            assert run.status == "awaiting_return"
            assert run.downloaded_by == members["admin"].id
            assert run.downloaded_at is not None
            downloaded_at = run.downloaded_at

            repeated = client.get(f"/api/school-leave/admin/runs/{run_id}/document")
            assert repeated.status_code == 200
            db.expire_all()
            run = db.get(SchoolLeaveRun, run_id)
            assert run is not None
            assert run.status == "awaiting_return"
            assert run.downloaded_at == downloaded_at
            assert client.post(f"/api/school-leave/admin/runs/{run_id}/cancel").status_code == 409
            assert client.delete(f"/api/school-leave/admin/runs/{run_id}").status_code == 409
            assert client.post(f"/api/school-leave/admin/runs/{run_id}/sent").status_code == 404

            summary = client.get("/api/school-leave/admin/summary")
            assert summary.status_code == 200
            assert summary.json() == {
                "ready_count": 0,
                "awaiting_return_count": 1,
                "todo_count": 1,
            }

            # Upload validation rejects mismatched MIME and oversized data.
            bad_mime = client.post(
                f"/api/school-leave/admin/runs/{run_id}/groups/0/result",
                files={"file": ("stamp.jpg", b"not-an-image", "text/plain")},
            )
            assert bad_mime.status_code == 400
            too_large = client.post(
                f"/api/school-leave/admin/runs/{run_id}/groups/0/result",
                files={
                    "file": (
                        "stamp.png",
                        b"x" * (SCHOOL_LEAVE_RESULT_MAX_BYTES + 1),
                        "image/png",
                    )
                },
            )
            assert too_large.status_code == 413

            # JPG stores privately under a random server name; one of two groups is not completion.
            jpg = client.post(
                f"/api/school-leave/admin/runs/{run_id}/groups/0/result",
                files={"file": ("teacher stamp.jpg", b"jpg-result", "image/jpeg")},
            )
            assert jpg.status_code == 200, jpg.text
            assert jpg.json()["available"] is True
            db.expire_all()
            result0 = db.scalar(
                select(SchoolLeaveGroupResult).where(
                    SchoolLeaveGroupResult.run_id == run_id,
                    SchoolLeaveGroupResult.group_index == 0,
                )
            )
            assert result0 is not None
            first_stored_name = result0.stored_name
            first_path = school_leave_result_file_path(first_stored_name)
            assert first_path.is_file()
            assert Path(first_stored_name).name == first_stored_name
            assert "teacher" not in first_stored_name
            assert result0.original_filename == "teacher stamp.jpg"
            assert result0.mime_type == "image/jpeg"
            assert result0.size_bytes == len(b"jpg-result")
            assert timedelta(hours=71, minutes=59) <= result0.expires_at - result0.uploaded_at <= timedelta(hours=72, minutes=1)
            assert db.get(SchoolLeaveRun, run_id).status == "awaiting_return"

            # Only students in group 0 and admins can read group 0.
            for key in ("a", "b"):
                set_actor(key)
                allowed = client.get(f"/api/school-leave/runs/{run_id}/groups/0/result")
                assert allowed.status_code == 200, (key, allowed.text)
                assert allowed.headers["content-type"].startswith("image/jpeg")
                assert str(run_id) not in allowed.headers["content-disposition"]
                assert "group" not in allowed.headers["content-disposition"].lower()
            for key in ("c", "d"):
                set_actor(key)
                assert client.get(f"/api/school-leave/runs/{run_id}/groups/0/result").status_code == 404
            set_actor("admin")
            assert client.get(f"/api/school-leave/runs/{run_id}/groups/0/result").status_code == 200

            # PNG on the remaining group makes every group complete automatically.
            png = client.post(
                f"/api/school-leave/admin/runs/{run_id}/groups/1/result",
                files={"file": ("returned.png", b"png-result", "image/png")},
            )
            assert png.status_code == 200, png.text
            db.expire_all()
            run = db.get(SchoolLeaveRun, run_id)
            assert run is not None
            assert run.status == "completed"
            assert client.get("/api/school-leave/admin/summary").json()["todo_count"] == 0

            set_actor("a")
            own_requests = client.get("/api/school-leave/requests")
            own = next(item for item in own_requests.json() if item["id"] == a_request_id)
            assert own["run_status"] == "completed"
            assert own["group_index"] == 0
            assert own["result_state"] == "available"
            set_actor("c")
            own_c = next(
                item
                for item in client.get("/api/school-leave/requests").json()
                if item["id"] == c_request_id
            )
            assert own_c["group_index"] == 1
            assert own_c["result_state"] == "available"

            # PDF replacement removes the old physical file and completed never regresses.
            set_actor("admin")
            pdf = client.post(
                f"/api/school-leave/admin/runs/{run_id}/groups/0/result",
                files={"file": ("replacement.pdf", b"%PDF-result", "application/pdf")},
            )
            assert pdf.status_code == 200, pdf.text
            db.expire_all()
            result0 = db.scalar(
                select(SchoolLeaveGroupResult).where(
                    SchoolLeaveGroupResult.run_id == run_id,
                    SchoolLeaveGroupResult.group_index == 0,
                )
            )
            assert result0 is not None
            assert result0.stored_name != first_stored_name
            assert not first_path.exists()
            pdf_path = school_leave_result_file_path(result0.stored_name)
            assert pdf_path.is_file()
            assert db.get(SchoolLeaveRun, run_id).status == "completed"
            pdf_get = client.get(f"/api/school-leave/runs/{run_id}/groups/0/result")
            assert pdf_get.status_code == 200
            assert pdf_get.headers["content-type"].startswith("application/pdf")
            assert "盖章.pdf" in pdf_get.headers["content-disposition"]

            # Expiration deletes files only, retains metadata and the completed business history.
            result1 = db.scalar(
                select(SchoolLeaveGroupResult).where(
                    SchoolLeaveGroupResult.run_id == run_id,
                    SchoolLeaveGroupResult.group_index == 1,
                )
            )
            assert result1 is not None
            png_path = school_leave_result_file_path(result1.stored_name)
            assert png_path.is_file()
            png_path.unlink()  # Missing files are also cleanup-idempotent.
            expired_at = school_leave_now() - timedelta(minutes=1)
            result0.expires_at = expired_at
            result1.expires_at = expired_at
            db.commit()

            cleaned = cleanup_expired_school_leave_results(db, now=school_leave_now())
            assert cleaned == 2
            assert cleanup_expired_school_leave_results(db, now=school_leave_now()) == 0
            db.expire_all()
            result0 = db.get(SchoolLeaveGroupResult, result0.id)
            result1 = db.get(SchoolLeaveGroupResult, result1.id)
            assert result0 is not None and result0.deleted_at is not None
            assert result1 is not None and result1.deleted_at is not None
            assert not pdf_path.exists()
            assert db.get(SchoolLeaveRun, run_id).status == "completed"

            set_actor("a")
            cleared_request = next(
                item
                for item in client.get("/api/school-leave/requests").json()
                if item["id"] == a_request_id
            )
            assert cleared_request["run_status"] == "completed"
            assert cleared_request["result_state"] == "cleared"
            assert client.get(f"/api/school-leave/runs/{run_id}/groups/0/result").status_code == 410

            # A completed run accepts replacement without regressing; delete then removes that file and rows.
            set_actor("admin")
            replacement = client.post(
                f"/api/school-leave/admin/runs/{run_id}/groups/0/result",
                files={"file": ("final.jpg", b"final-result", "image/jpeg")},
            )
            assert replacement.status_code == 200
            db.expire_all()
            current_result = db.scalar(
                select(SchoolLeaveGroupResult).where(
                    SchoolLeaveGroupResult.run_id == run_id,
                    SchoolLeaveGroupResult.group_index == 0,
                )
            )
            assert current_result is not None
            current_path = school_leave_result_file_path(current_result.stored_name)
            assert current_path.is_file()
            assert db.get(SchoolLeaveRun, run_id).status == "completed"

            run_request_ids = list(
                db.scalars(select(SchoolLeaveRequest.id).where(SchoolLeaveRequest.run_id == run_id))
            )
            deleted = client.delete(f"/api/school-leave/admin/runs/{run_id}")
            assert deleted.status_code == 204, deleted.text
            created_run_ids.remove(run_id)
            db.expire_all()
            assert db.get(SchoolLeaveRun, run_id) is None
            assert not current_path.exists()
            assert db.scalar(
                select(SchoolLeaveGroupResult.id).where(SchoolLeaveGroupResult.run_id == run_id)
            ) is None
            assert all(db.get(SchoolLeaveRequest, request_id) is None for request_id in run_request_ids)
            assert list(
                db.scalars(
                    select(SchoolLeaveRequest.id).where(
                        SchoolLeaveRequest.status == "included",
                        SchoolLeaveRequest.run_id.is_(None),
                    )
                )
            ) == []

            # A fresh one-group run completes after its only result is uploaded.
            single_request_id = submit("a", "2026-10-11T20:00:00", "2026-10-11T21:00:00")
            set_actor("admin")
            single = client.post("/api/school-leave/admin/runs/collect")
            assert single.status_code == 200
            single_run_id = single.json()["id"]
            created_run_ids.append(single_run_id)
            assert len(single.json()["groups"]) == 1
            assert client.get(f"/api/school-leave/admin/runs/{single_run_id}/document").status_code == 200
            uploaded_single = client.post(
                f"/api/school-leave/admin/runs/{single_run_id}/groups/0/result",
                files={"file": ("single.jpeg", b"single-result", "image/jpeg")},
            )
            assert uploaded_single.status_code == 200
            db.expire_all()
            assert db.get(SchoolLeaveRun, single_run_id).status == "completed"
            assert db.get(SchoolLeaveRequest, single_request_id).status == "included"

    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)
        with SessionLocal() as cleanup_db:
            if created_run_ids:
                cleanup_db.execute(
                    delete(SchoolLeaveRequest).where(SchoolLeaveRequest.run_id.in_(created_run_ids))
                )
                cleanup_db.execute(
                    delete(SchoolLeaveGroupResult).where(
                        SchoolLeaveGroupResult.run_id.in_(created_run_ids)
                    )
                )
                cleanup_db.execute(
                    delete(SchoolLeaveRun).where(SchoolLeaveRun.id.in_(created_run_ids))
                )
            if created_member_ids:
                cleanup_db.execute(delete(Member).where(Member.id.in_(created_member_ids)))
            cleanup_db.commit()

        if previous_phone is None:
            os.environ.pop("LEAVE_CONTACT_PHONE", None)
        else:
            os.environ["LEAVE_CONTACT_PHONE"] = previous_phone
        if previous_storage is None:
            os.environ.pop("SCHOOL_LEAVE_RESULT_STORAGE_DIR", None)
        else:
            os.environ["SCHOOL_LEAVE_RESULT_STORAGE_DIR"] = previous_storage
        storage.cleanup()

    print("School leave completion tests passed")


if __name__ == "__main__":
    main()
