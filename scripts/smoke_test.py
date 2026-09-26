import json
import os
import secrets
import sys
from http.cookiejar import CookieJar
from urllib.error import HTTPError
from urllib.request import HTTPCookieProcessor, Request, build_opener


BASE_URL = sys.argv[2].rstrip("/") if len(sys.argv) > 2 else "http://127.0.0.1"
ADMIN_EMAIL = "admin@example.com"
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


def login(email, password):
    client = opener()
    member = call(
        client,
        "/api/auth/login",
        method="POST",
        data={"email": email, "password": password},
    )
    assert member["email"] == email
    return client


def invite_and_activate(admin, name, email):
    invitation = call(
        admin,
        "/api/members/invite",
        method="POST",
        data={"name": name, "email": email, "role": "member"},
        expected=201,
    )
    token = invitation["invite_path"].rsplit("/", 1)[1]
    info = call(opener(), f"/api/invitations/{token}")
    assert info["name"] == name
    assert info["email"] == email

    password = secrets.token_urlsafe(18)
    call(
        opener(),
        f"/api/invitations/{token}/accept",
        method="POST",
        data={"password": password},
        expected=204,
    )
    call(opener(), f"/api/invitations/{token}", expected=404)
    return invitation["member"]["id"], password


def run_workflow():
    admin_password = os.environ["CI_ADMIN_PASSWORD"]

    call(opener(), "/api/auth/me", expected=401)
    call(opener(), "/api/tasks", expected=401)

    admin = login(ADMIN_EMAIL, admin_password)
    owner_id, owner_password = invite_and_activate(admin, "李四", "lisi@example.com")
    first_collaborator_id, first_collaborator_password = invite_and_activate(
        admin, "王五", "wangwu@example.com"
    )
    second_collaborator_id, _ = invite_and_activate(admin, "赵六", "zhaoliu@example.com")

    owner = login("lisi@example.com", owner_password)
    call(owner, "/api/members", expected=403)

    task = call(
        admin,
        "/api/tasks",
        method="POST",
        data={
            "title": TASK_TITLE,
            "deliverable": "完成物料清单核对并确认现场可用。",
            "owner_id": owner_id,
            "collaborator_ids": [first_collaborator_id, second_collaborator_id],
            "deadline": "2026-10-15T18:00:00",
            "status": "todo",
        },
        expected=201,
    )
    assert task["owner"]["id"] == owner_id
    assert {member["id"] for member in task["collaborators"]} == {
        first_collaborator_id,
        second_collaborator_id,
    }

    owner_tasks = call(owner, "/api/tasks?scope=mine")
    assert any(item["id"] == task["id"] for item in owner_tasks)

    collaborator = login("wangwu@example.com", first_collaborator_password)
    collaborator_tasks = call(collaborator, "/api/tasks?scope=mine")
    assert any(item["id"] == task["id"] for item in collaborator_tasks)
    call(
        collaborator,
        f"/api/tasks/{task['id']}",
        method="PATCH",
        data={"status": "doing"},
        expected=403,
    )

    updated = call(
        owner,
        f"/api/tasks/{task['id']}",
        method="PATCH",
        data={"status": "doing"},
    )
    assert updated["status"] == "doing"
    updated = call(
        owner,
        f"/api/tasks/{task['id']}",
        method="PATCH",
        data={"status": "done"},
    )
    assert updated["status"] == "done"

    print("V0.1 workflow smoke test passed")


def verify_persistence():
    admin = login(ADMIN_EMAIL, os.environ["CI_ADMIN_PASSWORD"])
    members = call(admin, "/api/members")
    emails = {member["email"] for member in members}
    assert {"lisi@example.com", "wangwu@example.com", "zhaoliu@example.com"} <= emails

    tasks = call(admin, "/api/tasks?scope=all")
    task = next(item for item in tasks if item["title"] == TASK_TITLE)
    assert task["status"] == "done"
    assert len(task["collaborators"]) == 2
    print("Database restart persistence check passed")


if __name__ == "__main__":
    phase = sys.argv[1] if len(sys.argv) > 1 else "workflow"
    if phase == "workflow":
        run_workflow()
    elif phase == "persistence":
        verify_persistence()
    else:
        raise SystemExit(f"unknown phase: {phase}")
