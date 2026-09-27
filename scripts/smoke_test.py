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
SECOND_MEMBER_EMAIL = "zhaoliu@example.com"
ROOT_TITLE = "春屿展示"
ROOT_FINAL_TITLE = "春屿展示（确认）"
CLAIM_CHILD_TITLE = "周边物资保障"
COLLAB_CHILD_TITLE = "现场摄影"
RELEASABLE_TITLE = "直播间值守"


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
        raise AssertionError(
            f"{method} {path}: expected {expected}, got {status}: {payload.decode()}"
        )

    if not payload:
        return None
    return json.loads(payload)


def upload_markdown(client, *, content=None, filename="ci-fixture.md", expected=201):
    boundary = "tarsgo-knowledge-smoke-boundary"
    if content is None:
        content = b"# CI fixture\nCurrent event material for authorization smoke."
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        "Content-Type: text/markdown\r\n\r\n"
    ).encode() + content + f"\r\n--{boundary}--\r\n".encode()
    request = Request(
        BASE_URL + "/api/knowledge/uploads",
        data=body,
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    try:
        with client.open(request, timeout=10) as response:
            payload = response.read()
            status = response.status
    except HTTPError as error:
        payload = error.read()
        status = error.code
    if status != expected:
        raise AssertionError(f"POST /api/knowledge/uploads: expected {expected}, got {status}: {payload.decode()}")
    return json.loads(payload) if payload else None


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


def create_task(manager, **overrides):
    payload = {
        "title": "默认运营任务",
        "deliverable": "",
        "owner_id": None,
        "owner_claimable": True,
        "collaborator_ids": [],
        "collaboration_open": False,
        "parent_id": None,
        "deadline": "2026-10-15T18:00:00",
        "status": "todo",
    }
    payload.update(overrides)
    return call(manager, "/api/tasks", method="POST", data=payload, expected=201)


def run_workflow():
    admin_password = os.environ["CI_ADMIN_PASSWORD"]

    call(opener(), "/api/auth/me", expected=401)
    call(opener(), "/api/tasks?scope=all", expected=401)
    call(opener(), "/api/members", expected=401)
    call(opener(), "/api/knowledge", expected=401)
    call(opener(), "/api/knowledge/options", expected=401)
    call(opener(), "/api/knowledge/sync/github", method="POST", expected=401)

    admin = login(ADMIN_EMAIL, admin_password)
    assert isinstance(call(admin, "/api/knowledge"), list)
    uploaded_knowledge = upload_markdown(admin)
    assert uploaded_knowledge["title"] == "ci-fixture"
    knowledge_options = call(admin, "/api/knowledge/options")
    assert any(option["id"] == uploaded_knowledge["id"] for option in knowledge_options)
    upload_markdown(admin, content=b"x" * (10 * 1024 * 1024 + 64 * 1024), filename="too-large.txt", expected=413)
    call(admin, f"/api/knowledge/{uploaded_knowledge['id']}", method="DELETE", expected=204)

    manager_invite = invite(admin, "王五", MANAGER_EMAIL, "manager")
    manager_id = manager_invite["member"]["id"]
    manager_password = activate(manager_invite)

    owner_invite = invite(admin, "李四", OWNER_EMAIL)
    owner_id = owner_invite["member"]["id"]
    owner_password = activate(owner_invite)

    second_invite = invite(admin, "赵六", SECOND_MEMBER_EMAIL)
    second_id = second_invite["member"]["id"]
    second_password = activate(second_invite)

    manager = login(MANAGER_EMAIL, manager_password)
    owner = login(OWNER_EMAIL, owner_password)
    second = login(SECOND_MEMBER_EMAIL, second_password)

    call(manager, "/api/members", expected=403)
    call(manager, "/api/knowledge", expected=403)
    call(manager, "/api/knowledge/options", expected=403)
    call(manager, "/api/knowledge/sync/github", method="POST", expected=403)
    call(manager, "/api/knowledge/999999", method="DELETE", expected=403)
    upload_markdown(manager, expected=403)
    call(owner, "/api/members", expected=403)
    call(owner, "/api/tasks/assignees", expected=403)

    assignees = call(manager, "/api/tasks/assignees")
    assert {item["id"] for item in assignees} >= {manager_id, owner_id, second_id}

    call(
        manager,
        "/api/tasks",
        method="POST",
        data={
            "title": "无负责人且不可认领",
            "deliverable": "",
            "owner_id": None,
            "owner_claimable": False,
            "collaborator_ids": [],
            "collaboration_open": False,
            "parent_id": None,
            "deadline": "2026-10-15T18:00:00",
            "status": "todo",
        },
        expected=422,
    )

    root = create_task(
        manager,
        title=ROOT_TITLE,
        deliverable="完成展示现场整体执行。",
        owner_id=manager_id,
        owner_claimable=False,
        collaborator_ids=[second_id],
        collaboration_open=False,
        deadline="2026-09-21T18:00:00",
    )
    assert root["parent_id"] is None
    assert root["owner"]["id"] == manager_id

    claim_child = create_task(
        manager,
        title=CLAIM_CHILD_TITLE,
        parent_id=root["id"],
        owner_id=None,
        owner_claimable=True,
        collaboration_open=True,
        deadline="2026-09-21T15:00:00",
    )
    assert claim_child["parent_id"] == root["id"]
    assert claim_child["owner"] is None
    assert claim_child["owner_claimable"] is True

    collaboration_child = create_task(
        manager,
        title=COLLAB_CHILD_TITLE,
        parent_id=root["id"],
        owner_id=manager_id,
        owner_claimable=False,
        collaboration_open=True,
        deadline="2026-09-21T17:00:00",
    )

    call(
        manager,
        "/api/tasks",
        method="POST",
        data={
            "title": "不允许的二级分工",
            "deliverable": "",
            "owner_id": manager_id,
            "owner_claimable": False,
            "collaborator_ids": [],
            "collaboration_open": False,
            "parent_id": claim_child["id"],
            "deadline": "2026-09-21T16:00:00",
            "status": "todo",
        },
        expected=400,
    )

    all_for_owner = call(owner, "/api/tasks?scope=all")
    all_ids = {item["id"] for item in all_for_owner}
    assert {root["id"], claim_child["id"], collaboration_child["id"]} <= all_ids

    call(
        owner,
        f"/api/tasks/{root['id']}",
        method="PATCH",
        data={"title": "成员不应能修改结构"},
        expected=403,
    )

    waiting = call(owner, "/api/tasks?scope=claimable")
    assert claim_child["id"] in {item["id"] for item in waiting}

    claimed = call(second, f"/api/tasks/{claim_child['id']}/claim", method="POST")
    assert claimed["owner"]["id"] == second_id
    call(owner, f"/api/tasks/{claim_child['id']}/claim", method="POST", expected=409)

    joined = call(owner, f"/api/tasks/{collaboration_child['id']}/collaborators/join", method="POST")
    assert owner_id in {item["id"] for item in joined["collaborators"]}
    left = call(owner, f"/api/tasks/{collaboration_child['id']}/collaborators/leave", method="POST")
    assert owner_id not in {item["id"] for item in left["collaborators"]}

    reassigned = call(
        manager,
        f"/api/tasks/{claim_child['id']}",
        method="PATCH",
        data={"owner_id": owner_id},
    )
    assert reassigned["owner"]["id"] == owner_id

    updated_by_owner = call(
        owner,
        f"/api/tasks/{claim_child['id']}",
        method="PATCH",
        data={"status": "doing"},
    )
    assert updated_by_owner["status"] == "doing"
    call(
        second,
        f"/api/tasks/{claim_child['id']}",
        method="PATCH",
        data={"status": "done"},
        expected=403,
    )

    releasable = create_task(
        manager,
        title=RELEASABLE_TITLE,
        owner_id=None,
        owner_claimable=True,
        collaboration_open=False,
        deadline="2026-09-21T16:30:00",
    )
    claimed_by_owner = call(owner, f"/api/tasks/{releasable['id']}/claim", method="POST")
    assert claimed_by_owner["owner"]["id"] == owner_id
    released = call(owner, f"/api/tasks/{releasable['id']}/unclaim", method="POST")
    assert released["owner"] is None
    assert released["owner_claimable"] is True

    call(owner, f"/api/tasks/{releasable['id']}/claim", method="POST")
    call(
        owner,
        f"/api/tasks/{releasable['id']}",
        method="PATCH",
        data={"status": "done"},
    )
    call(owner, f"/api/tasks/{releasable['id']}/unclaim", method="POST", expected=409)

    disabled = call(admin, f"/api/members/{second_id}/disable", method="POST")
    assert disabled["status"] == "disabled"
    call(second, "/api/auth/me", expected=401)
    login(SECOND_MEMBER_EMAIL, second_password, expected=403)

    disabled_target = create_task(
        manager,
        title="停用成员不可认领",
        owner_id=None,
        owner_claimable=True,
        deadline="2026-09-22T12:00:00",
    )
    call(second, f"/api/tasks/{disabled_target['id']}/claim", method="POST", expected=401)

    root_updated = call(
        manager,
        f"/api/tasks/{root['id']}",
        method="PATCH",
        data={"title": ROOT_FINAL_TITLE},
    )
    assert root_updated["title"] == ROOT_FINAL_TITLE
    assert [item["id"] for item in root_updated["collaborators"]] == [second_id]

    all_after = call(owner, "/api/tasks?scope=all")
    root_after = next(item for item in all_after if item["id"] == root["id"])
    children = [item for item in all_after if item["parent_id"] == root["id"]]
    assert root_after["parent_id"] is None
    assert {item["title"] for item in children} >= {CLAIM_CHILD_TITLE, COLLAB_CHILD_TITLE}

    print("V0.2 operations workflow smoke test passed")


def verify_persistence():
    admin = login(ADMIN_EMAIL, os.environ["CI_ADMIN_PASSWORD"])
    members = call(admin, "/api/members")
    by_email = {member["email"]: member for member in members}
    assert by_email[MANAGER_EMAIL]["status"] == "active"
    assert by_email[OWNER_EMAIL]["status"] == "active"
    assert by_email[SECOND_MEMBER_EMAIL]["status"] == "disabled"

    tasks = call(admin, "/api/tasks?scope=all")
    root = next(item for item in tasks if item["title"] == ROOT_FINAL_TITLE)
    claim_child = next(item for item in tasks if item["title"] == CLAIM_CHILD_TITLE)
    collaboration_child = next(item for item in tasks if item["title"] == COLLAB_CHILD_TITLE)
    releasable = next(item for item in tasks if item["title"] == RELEASABLE_TITLE)

    assert root["parent_id"] is None
    assert by_email[SECOND_MEMBER_EMAIL]["id"] in {
        item["id"] for item in root["collaborators"]
    }
    assert claim_child["parent_id"] == root["id"]
    assert claim_child["owner"]["id"] == by_email[OWNER_EMAIL]["id"]
    assert claim_child["status"] == "doing"
    assert collaboration_child["parent_id"] == root["id"]
    assert collaboration_child["collaboration_open"] is True
    assert releasable["status"] == "done"

    print("V0.2 database restart persistence check passed")


if __name__ == "__main__":
    phase = sys.argv[1] if len(sys.argv) > 1 else "workflow"
    if phase == "workflow":
        run_workflow()
    elif phase == "persistence":
        verify_persistence()
    else:
        raise SystemExit(f"unknown phase: {phase}")
