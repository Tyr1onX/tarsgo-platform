"""MySQL-backed coverage for the independent camp leave collection workflow."""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.auth import get_current_member
from app.db import SessionLocal, get_db
from app.main import app
from app.models import CampLeaveEvent, CampLeaveParticipant, Member


def future_payload(event_type: str = "winter", *, deadline: datetime | None = None) -> dict[str, str]:
    now = datetime.now(ZoneInfo("Asia/Shanghai")).replace(tzinfo=None, second=0, microsecond=0)
    start = (now + timedelta(days=20)).date()
    end = start + timedelta(days=6)
    collection_deadline = deadline or now + timedelta(days=10)
    return {
        "title": "测试冬令营" if event_type == "winter" else "测试夏令营",
        "type": event_type,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "collection_deadline": collection_deadline.isoformat(timespec="minutes"),
    }


def main() -> None:
    suffix = uuid4().hex
    admin_email = f"camp-admin-{suffix}@example.invalid"
    formal_email = f"camp-formal-{suffix}@example.invalid"
    reserve_email = f"camp-reserve-{suffix}@example.invalid"
    incomplete_email = f"camp-incomplete-{suffix}@example.invalid"
    event_ids: set[int] = set()
    previous_overrides = dict(app.dependency_overrides)

    with SessionLocal() as db:
        admin = Member(name="测试管理员", email=admin_email, role="admin", status="active")
        formal = Member(
            name="测试成员甲",
            email=formal_email,
            student_id="26000101",
            college="electronic-science-engineering",
            team_membership="formal",
            role="member",
            status="active",
        )
        reserve = Member(
            name="Test Member B",
            email=reserve_email,
            student_id="26000102",
            college="artificial-intelligence",
            team_membership="reserve",
            role="member",
            status="active",
        )
        incomplete = Member(
            name="资料未全",
            email=incomplete_email,
            student_id=None,
            college=None,
            team_membership="formal",
            role="member",
            status="active",
        )
        db.add_all([admin, formal, reserve, incomplete])
        db.commit()
        db.refresh(admin)
        db.refresh(formal)
        db.refresh(reserve)
        db.refresh(incomplete)

        def override_database():
            yield db

        app.dependency_overrides[get_db] = override_database
        actor: Member | None = None

        def set_actor(member: Member | None) -> None:
            nonlocal actor
            actor = member
            if member is None:
                app.dependency_overrides.pop(get_current_member, None)
            else:
                app.dependency_overrides[get_current_member] = lambda: actor

        client = TestClient(app)
        try:
            # Creation is admin-only; both event types are supported and date order is enforced.
            set_actor(formal)
            assert client.post("/api/camp-leave/admin/events", json=future_payload()).status_code == 403
            set_actor(admin)
            invalid_dates = future_payload()
            invalid_dates["start_date"], invalid_dates["end_date"] = invalid_dates["end_date"], invalid_dates["start_date"]
            assert client.post("/api/camp-leave/admin/events", json=invalid_dates).status_code == 422

            winter = client.post("/api/camp-leave/admin/events", json=future_payload("winter"))
            assert winter.status_code == 201, winter.text
            winter_event = winter.json()
            winter_id = winter_event["id"]
            event_ids.add(winter_id)
            token = winter_event["public_path"].rsplit("/", 1)[1]
            assert 40 <= len(token) <= 50
            assert set(token) <= set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")
            assert winter_event["type"] == "winter"
            assert winter_event["status"] == "collecting"
            assert winter_event["participant_count"] == 0

            summer = client.post("/api/camp-leave/admin/events", json=future_payload("summer"))
            assert summer.status_code == 201, summer.text
            event_ids.add(summer.json()["id"])
            assert summer.json()["type"] == "summer"

            # Profile values are snapshotted. Members see their own state, never counts or lists.
            set_actor(formal)
            member_events = client.get("/api/camp-leave/events")
            assert member_events.status_code == 200
            assert "participant_count" not in member_events.json()[0]
            assert "public_path" not in member_events.json()[0]
            joined_formal = client.post(f"/api/camp-leave/events/{winter_id}/join")
            assert joined_formal.status_code == 201, joined_formal.text
            assert joined_formal.json()["joined"] is True
            assert joined_formal.json()["participant_type"] == "formal"

            set_actor(reserve)
            joined_reserve = client.post(f"/api/camp-leave/events/{winter_id}/join")
            assert joined_reserve.status_code == 201, joined_reserve.text
            assert joined_reserve.json()["participant_type"] == "reserve"
            duplicate_member = client.post(f"/api/camp-leave/events/{winter_id}/join")
            assert duplicate_member.status_code == 409

            set_actor(incomplete)
            incomplete_join = client.post(f"/api/camp-leave/events/{winter_id}/join")
            assert incomplete_join.status_code == 400
            assert "完善个人资料" in incomplete_join.json()["detail"]

            # External participants can only submit their three fields; their type is server-fixed to other.
            set_actor(None)
            public_info = client.get(f"/api/camp-leave/public/{token}")
            assert public_info.status_code == 200
            public_json = public_info.json()
            assert public_json["title"] == winter_event["title"]
            assert not {"id", "participants", "groups", "participant_count", "public_token"}.intersection(public_json)
            assert client.get(f"/api/camp-leave/admin/events/{winter_id}").status_code == 401

            external_payload = {
                "name": "校外参与者",
                "student_id": "26000103",
                "college": "electronic-science-engineering",
            }
            public_join = client.post(f"/api/camp-leave/public/{token}/participants", json=external_payload)
            assert public_join.status_code == 201, public_join.text
            assert public_join.json() == {"submitted": True}
            assert client.post(
                f"/api/camp-leave/public/{token}/participants",
                json={**external_payload, "participant_type": "formal"},
            ).status_code == 422
            assert client.post(
                f"/api/camp-leave/public/{token}/participants",
                json={**external_payload, "student_id": "１２３４５６７８"},
            ).status_code == 422
            assert client.post(
                f"/api/camp-leave/public/{token}/participants",
                json={**external_payload, "college": "not-a-college"},
            ).status_code == 422
            duplicate_student = client.post(
                f"/api/camp-leave/public/{token}/participants",
                json={**external_payload, "name": "另一个人"},
            )
            assert duplicate_student.status_code == 409

            # A member may cancel and rejoin while collecting.
            set_actor(reserve)
            canceled = client.post(f"/api/camp-leave/events/{winter_id}/leave")
            assert canceled.status_code == 200
            assert canceled.json()["joined"] is False
            assert client.post(f"/api/camp-leave/events/{winter_id}/join").status_code == 201

            # A public link exposes only event basics; grouped participant details are admin-only.
            set_actor(admin)
            detail_response = client.get(f"/api/camp-leave/admin/events/{winter_id}")
            assert detail_response.status_code == 200, detail_response.text
            detail = detail_response.json()
            groups = {group["college"]: group for group in detail["groups"]}
            assert groups["electronic-science-engineering"]["count"] == 2
            assert {row["participant_type"] for row in groups["electronic-science-engineering"]["participants"]} == {"formal", "other"}
            assert groups["artificial-intelligence"]["count"] == 1
            assert groups["artificial-intelligence"]["participants"][0]["participant_type"] == "reserve"
            assert detail["event"]["public_path"] == winter_event["public_path"]

            # Admin may remove a bad record during collection.
            other_row = next(
                row for group in detail["groups"] for row in group["participants"] if row["participant_type"] == "other"
            )
            assert client.delete(
                f"/api/camp-leave/admin/events/{winter_id}/participants/{other_row['id']}"
            ).status_code == 204

            # Updating the profile later does not mutate the submitted snapshots.
            formal.name = "后续改名"
            formal.student_id = "26000991"
            formal.college = "art"
            formal.team_membership = "reserve"
            db.commit()
            db.expire_all()
            detail = client.get(f"/api/camp-leave/admin/events/{winter_id}").json()
            saved_formal = next(
                row for group in detail["groups"] for row in group["participants"] if row["participant_type"] == "formal"
            )
            assert saved_formal["name"] == "测试成员甲"
            assert saved_formal["student_id"] == "26000101"
            assert saved_formal["college"] == "electronic-science-engineering"

            # Closed events are immutable for members, public submissions, and admin cleanup.
            closed = client.post(f"/api/camp-leave/admin/events/{winter_id}/close")
            assert closed.status_code == 200
            assert closed.json()["status"] == "closed"
            set_actor(formal)
            assert client.post(f"/api/camp-leave/events/{winter_id}/join").status_code == 409
            assert client.post(f"/api/camp-leave/events/{winter_id}/leave").status_code == 409
            set_actor(admin)
            assert client.delete(
                f"/api/camp-leave/admin/events/{winter_id}/participants/{saved_formal['id']}"
            ).status_code == 409
            set_actor(None)
            closed_public = client.get(f"/api/camp-leave/public/{token}")
            assert closed_public.status_code == 200
            assert closed_public.json()["accepting_participants"] is False
            assert client.post(
                f"/api/camp-leave/public/{token}/participants",
                json={"name": "截止后报名", "student_id": "26000109", "college": "art"},
            ).status_code == 409

            # Deadline is enforced even before an admin changes the event's status.
            expired = future_payload("summer", deadline=datetime.now(ZoneInfo("Asia/Shanghai")).replace(tzinfo=None) - timedelta(minutes=1))
            expired_event = client.post("/api/camp-leave/admin/events", json=expired)
            # No anonymous creation: event creation remains admin-only.
            assert expired_event.status_code == 401
            set_actor(admin)
            expired_event = client.post("/api/camp-leave/admin/events", json=expired)
            assert expired_event.status_code == 201
            expired_id = expired_event.json()["id"]
            event_ids.add(expired_id)
            expired_token = expired_event.json()["public_path"].rsplit("/", 1)[1]
            set_actor(None)
            assert client.post(
                f"/api/camp-leave/public/{expired_token}/participants",
                json={"name": "已过截止", "student_id": "26000110", "college": "art"},
            ).status_code == 409

            set_actor(None)
            assert client.get("/api/camp-leave/public/not-a-token").status_code == 404
        finally:
            app.dependency_overrides.clear()
            app.dependency_overrides.update(previous_overrides)
            db.execute(delete(CampLeaveParticipant).where(CampLeaveParticipant.event_id.in_(event_ids)))
            if event_ids:
                db.execute(delete(CampLeaveEvent).where(CampLeaveEvent.id.in_(event_ids)))
            db.execute(delete(Member).where(Member.email.in_([admin_email, formal_email, reserve_email, incomplete_email])))
            db.commit()

    print("Camp Leave V1 workflow tests passed")


if __name__ == "__main__":
    main()
