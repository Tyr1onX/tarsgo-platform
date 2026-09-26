import json
import os
import secrets
import sys
from http.cookiejar import CookieJar
from urllib.error import HTTPError
from urllib.request import HTTPCookieProcessor, Request, build_opener


BASE_URL = sys.argv[2].rstrip("/") if len(sys.argv) > 2 else "http://127.0.0.1"
ADMIN_EMAIL = "admin@example.com"
MANAGER_EMAIL = "manager@example.com"
OWNER_EMAIL = "lisi@example.com"
TASK_TITLE = "整理招新现场物料"


def opener():
    return build_opener(HTTPCookieProcessor(CookieJar()))


def call(client, path, *, method="GET", data=None, expected=200):
    body = None if data is None else json.dumps(data).encode()
    request = Request(
        BASE_URL + path,
        data=body,
        method=method,
        headers={"Content-Type": "application/json"} if body is not None else {},
    )
    try:
        with client.open(request, timeout=10) as response:
            payload = response.read()
            status = response.status
    except HTTPError as error:
        payload = error.read()
        status = error.code

    if status != expected:
        raise AssertionError(f"{method} {path}: expected {expected}, got {status}: {payload.decode()}")

    if not payload:
        return None
    return json.loads(payload)


def login(email, password, *, expected=200):
    client = opener()
    result = call(
        client,
        "/api/auth/login",
        method="POST",
        data={"email": email, "password": password},
        expected=expected,
    )
    if expected == 200:
        assert result["email"] == email
    return client


def invite(admin, name, email, role="member"):
    return call(
        admin,
        "/api/members/invite",
        method="POST",
        data={"name": name, "email": email, "role": role},
        expected=201,
    )


def activate(invitation):
    token = invitation["invite_path"].rsplit("/", 1)[1]
    info = call(opener(), f"/api/invitations/{token}")
    assert info["name"] == invitation["member"]["name"]
    assert info["email"] == invitation["member"]["email"]
    password = secrets.token_urlsafe(18)
    call(
        opener(),
        f"/api/invitations/{token}/accept",
        method="POST",
        data={"password": password},
        expected=204,
    )
    call(opener(), f"/api/invitations/{token}", expected=404)
    return password


def run_workflow():
    admin_password = os.environ["CI_ADMIN_PASSWORD"]

    call(opener(), "/api/auth/me", expected=401)
    call(opener(), "/api/tasks", expected=401)
    call(opener(), "/api/members", expected=401)

    admin = login(ADMIN_EMAIL, admin_password)

    manager_invite = invite(admin, "王五", MANAGER_EMAIL, "manager")
    manager_id = manager_invite["member"]["id"]
    manager_password = activate(manager_invite)

    owner_invite = invite(admin, "李四", OWNER_EMAIL)
    owner_id = owner_invite["member"]["id"]
    owner_password = activate(owner_invite)

    collaborator_invite = invite(admin, "赵六", "zhaoliu@example.com")
    collaborator_id = collaborator_invite["member"]["id"]
    collaborator_password = activate(collaborator_invite)

    pending_invite = invite(admin, "钱七", "qianqi@example.com")
    pending_id = pending_invite["member"]["id"]
    call(admin, f"/api/members/{pending_id}/enable", method="POST", expected=409)

    manager = login(MANAGER_EMAIL, manager_password)
    member = login(OWNER_EMAIL, owner_password)
    collaborator = login("zhaoliu@example.com", collaborator_password)

    call(manager, "/api/members", expected=403)
    call(
        manager,
        "/api/members/invite",
        method="POST",
        data={"name": "孙八", "email": "sunba@example.com", "role": "member"},
        expected=403,
    )
    call(
        manager,
        "/api/members/invite",
        method="POST",
        data={"name": "周九", "email": "zhoujiu@example.com", "role": "admin"},
        expected=403,
    )
    call(manager, f"/api/members/{owner_id}/disable", method="POST", expected=403)
    call(member, "/api/members", expected=403)

    assignees = call(manager, "/api/tasks/assignees")
    assert {item["id"] for item in assignees} >= {manager_id, owner_id, collaborator_id}
    assert all(set(item) == {"id", "name"} for item in assignees)

    task = call(
        manager,
        "/api/tasks",
        method="POST",
        data={
            "title": TASK_TITLE,
            "deliverable": "完成物料清单核对并确认现场可用。",
            "owner_id": owner_id,
            "collaborator_ids": [collaborator_id],
            "deadline": "2026-10-15T18:00:00",
            "status": "todo",
        },
        expected=201,
    )
    updated_by_manager = call(
        manager,
        f"/api/tasks/{task['id']}",
        method="PATCH",
        data={"deliverable": "完成物料清单核对、现场确认并归档。"},
    )
    assert updated_by_manager["deliverable"].endswith("归档。")

    assert any(item["id"] == task["id"] for item in call(member, "/api/tasks?scope=mine"))
    assert any(item["id"] == task["id"] for item in call(collaborator, "/api/tasks?scope=mine"))
    call(
        collaborator,
        f"/api/tasks/{task['id']}",
        method="PATCH",
        data={"status": "doing"},
        expected=403,
    )

    call(
        member,
        f"/api/tasks/{task['id']}",
        method="PATCH",
        data={"status": "doing"},
    )

    disabled = call(admin, f"/api/members/{owner_id}/disable", method="POST")
    assert disabled["status"] == "disabled"
    call(member, "/api/auth/me", expected=401)
    login(OWNER_EMAIL, owner_password, expected=403)

    enabled = call(admin, f"/api/members/{owner_id}/enable", method="POST")
    assert enabled["status"] == "active"
    member = login(OWNER_EMAIL, owner_password)
    assert call(member, "/api/auth/me")["email"] == OWNER_EMAIL

    updated = call(
        member,
        f"/api/tasks/{task['id']}",
        method="PATCH",
        data={"status": "done"},
    )
    assert updated["status"] == "done"

    print("V0.1 hardening workflow smoke test passed")


def verify_persistence():
    admin = login(ADMIN_EMAIL, os.environ["CI_ADMIN_PASSWORD"])
    members = call(admin, "/api/members")
    by_email = {member["email"]: member for member in members}
    assert by_email[MANAGER_EMAIL]["role"] == "manager"
    assert by_email[OWNER_EMAIL]["status"] == "active"
    assert by_email["qianqi@example.com"]["status"] == "invited"

    tasks = call(admin, "/api/tasks?scope=all")
    task = next(item for item in tasks if item["title"] == TASK_TITLE)
    assert task["status"] == "done"
    assert task["deliverable"].endswith("归档。")
    assert len(task["collaborators"]) == 1
    print("Database restart persistence check passed")


if __name__ == "__main__":
    phase = sys.argv[1] if len(sys.argv) > 1 else "workflow"
    if phase == "workflow":
        run_workflow()
    elif phase == "persistence":
        verify_persistence()
    else:
        raise SystemExit(f"unknown phase: {phase}")
