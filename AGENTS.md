# AGENTS.md

## Product goal

TARS-Go is an open-source **public operations collaboration board** for university robotics teams.

Current product scope is shared external / operations work such as promotion, event execution, recruitment, materials, livestreaming and photography.

Discussion belongs in WeChat, meetings or offline conversation. TARS-Go records work that has already been clarified and keeps the current execution state accurate.

Do not turn the current product into a generic Todo app or a technical R&D management system.

Read docs/operations-workflow.md and docs/ai-direction.md before expanding the task model.

## Working rules

1. Read current code before making architectural decisions. Code is the source of truth; docs describe intended boundaries.
2. Prefer the smallest implementation that completes a real workflow.
3. Keep one implementation path and one source of truth for each state.
4. Do not add abstractions, dependencies, services or compatibility layers without a current requirement.
5. Fix root causes instead of layering patches.
6. Remove obsolete code when a new implementation replaces it.
7. Keep changes scoped to the current requirement.
8. Never commit production secrets or real private team/member data.
9. Published work may continue to change. Do not model publication as permanent immutability.
10. Keep operation cost low. A simple execution assignment should not require filling many advanced fields.

## Architecture

~~~text
Browser
  |
Caddy
  |-- Vue static frontend
  |
  +-- /api/* -> FastAPI -> MySQL
~~~

Deployment target: one VPS with Docker Compose. The API container runs Alembic migrations before FastAPI starts.

Do not introduce Redis, queues, microservices, Kubernetes, a separate API gateway, multiple databases or deployment control panels without a demonstrated requirement.

## Current stack

- Vue 3 + TypeScript + Vite
- FastAPI
- SQLAlchemy + PyMySQL
- Alembic
- MySQL 8.4 LTS
- Caddy
- Docker Compose

Frontend dependencies are locked with package-lock.json; Docker and CI use npm ci.

## Current V0.2 scope

Implement only:

- operations item + one level of execution tasks
- team-wide visibility of published operations work
- direct owner assignment
- public owner claiming
- specified collaborators
- open collaboration join / leave
- current task status

Do not add a second Activity model. Continue evolving Task.

The V0.2 second-stage first slice adds only an allowlisted admin AI draft planner and transactional batch confirmation. Do not expand it into automatic scheduling, member recommendation, time-conflict algorithms, workload algorithms, knowledge retrieval, notifications, comments, files, leave, weekly reports, technical R&D workflows, complex dashboards or complex organization structures.

## Task model boundary

A root Task is an operations item. A task with parent_id is one execution assignment under a root item.

Only one child level is supported. Reject grandchildren.

Current task structure:

- parent_id: nullable self-reference
- title
- deliverable: optional completion standard stored as text
- owner_id: nullable
- owner_claimable
- collaborators through task_collaborators
- collaboration_open
- explicit deadline
- todo | doing | done

A published task must satisfy:

~~~text
owner_id IS NOT NULL
OR
owner_claimable = true
~~~

Do not store child tasks or collaborator IDs in JSON.

Child creation may prefill the parent's deadline in the frontend, but the child must save its own explicit deadline. Do not add hidden inheritance.

Historical tasks may retain references to disabled members. Do not revalidate unchanged historical assignments during unrelated edits. Newly submitted owners and collaborators must be active.

## Task granularity

When deciding whether work should be one task or several, use:

- time
- location
- personnel continuity
- handoff points
- completion standard

Actions on one responsibility chain that are naturally completed continuously may stay together.

Work that happens simultaneously and cannot be performed by one person should be split.

Creating a root item does not require defining all future child tasks. Child tasks may be added later as execution becomes clear.

## Visibility and claiming

All active members may read all published operations items and child tasks.

GET /api/tasks supports:

- scope=mine
- scope=claimable
- scope=all

Do not restore the old restriction that scope=all is manager-only.

Owner claiming must remain atomic. Do not implement claim as a read-then-write sequence that can allow two owners.

An active member may:

- claim an ownerless, non-completed task when owner_claimable=true
- cancel their own claim only while the task is non-completed and remains owner-claimable
- join / leave a non-completed task when collaboration_open=true

The current owner is not duplicated in collaborators.

## Authorization boundary

System roles are admin, manager and member. Real-world titles are not system roles.

### admin

- member account management
- all operations task management
- normal active-member claim / collaboration actions

### manager

- all operations task management
- no member account management
- normal active-member claim / collaboration actions

### member

- read all published operations work
- read mine and claimable views
- claim / unclaim eligible owner slots
- join / leave open collaboration
- update execution status only when currently responsible
- no structural task editing

Only admin may list full member account data, create invitations, regenerate invitations, disable/enable accounts or create system-role accounts.

Use require_admin for account management and require_manager for admin/manager-only task structure operations.

Backend authorization is authoritative; frontend hiding is convenience only.

## Authentication and member state

Passwords use Argon2 through pwdlib.

Login uses a random opaque HttpOnly cookie with SameSite=Lax. Only SHA-256 session-token hashes are stored in MySQL. Production HTTPS requires Secure cookies.

Invitation tokens are random opaque values; only their hashes are stored. They expire after seven days and are removed immediately after activation.

Member states are invited, active and disabled.

Only active accounts may act on tasks. Disabling deletes existing sessions immediately. Enabling restores a previously active account without creating a session.

## Database migrations

Current migration chain:

~~~text
0001_v0_1
-> 0002_operations_claiming
-> 0003_ai_planner_usage
~~~

Migrations must preserve current production rows. Never clear or silently rewrite production data to simplify a schema change.

V0.2 migration keeps existing owners and completion standards, makes owner_id nullable and adds the new operations fields with safe defaults.

CI must keep a real seeded 0001 -> head migration compatibility check.

## Backend boundaries

~~~text
app/
├── auth.py
├── bootstrap_admin.py
├── db.py
├── main.py
├── models.py
├── schemas.py
└── routers/
    ├── ai_planner.py
    ├── auth.py
    ├── invitations.py
    ├── members.py
    └── tasks.py
~~~

Do not add controller/service/repository/facade layers without a concrete boundary that needs them.

## Frontend boundaries

The frontend intentionally has no UI framework, router library or state-management library.

Primary routes are /login, /invite/:token, /, /tasks, /team and /me. /ai-planner is an allowlisted admin-only workflow entry and must not become a global navigation destination.

Keep one task entry: /tasks.

Every active member sees three task views:

- 我的
- 待认领
- 全部

admin / manager management controls live on the same task page. Do not recreate a separate management destination.

/team is admin-only member account management.

/me is personal information, role and logout only.

Home answers “what do I need to do now?” with the user's unfinished owned / collaboration work plus a lightweight pending-claim entry. Do not add team statistics.

Mobile is the primary layout. PC uses the same responsive UI.

Do not split App.vue only for stylistic reasons. Do not add a UI framework, Pinia, a router migration, dashboard statistics or decorative controls without a real workflow need.

## AI planner boundary

AI is a structured-advice layer, not a fact source.

The current implemented flow is:

~~~text
natural-language requirement
-> one structured AI draft
-> human edits / removes / adds draft work
-> backend validation
-> explicit confirmation
-> transactional root item + first-level assignments
~~~

Only allowlisted admins may generate plans. AI access is checked server-side by role, member ID allowlist, enabled flag and server configuration. The provider key never leaves the API container.

Generation must remain one model request per explicit Generate / Regenerate action. No agent loop, hidden retry loop, automatic reflection, history, database task dump, RAG or files. Input is capped at 5000 characters, output at 15 assignments / 6 questions and 2200 output tokens, and the official SDK is configured with max_retries=0.

The persistent ai_planner_daily_usage table stores only daily request and aggregate token counts. Never store full planner prompts or generated drafts there.

The AI schema may contain titles, completion standards, a tentative item deadline, owner_claimable, collaboration_open and confirmation questions. It must never contain owner_id or choose real members.

Draft generation never writes Task rows. Only explicit confirmation calls the normal task batch endpoint. The confirming user owns the root item; a child with owner_claimable=true is published ownerless, while a child with owner_claimable=false is temporarily owned by the confirming manager/admin. Database state, permissions and constraints remain deterministic backend logic.

Do not expand this slice into automatic scheduling, member recommendation, workload scoring, conflict detection, dependencies, knowledge retrieval or AI changes to already-published tasks.

## Change history direction

Published tasks remain editable. V0.2 does not implement a full audit log.

A later stage should record important changes to fields such as owner, deadline, completion standard, claiming status and handoff-relevant structure. Do not fake this with free-form comments in the current stage.

## Public data boundary

Never commit .env, passwords, tokens, API keys, private keys, server IPs, database files/backups, real personal information, private team notes or internal operational records.

Use fictional data for tests and documentation. CI passwords must be generated at runtime.

Git commit author metadata is outside repository file-content scope; do not rewrite history to hide it.

## Validation

The V0.2 GitHub Actions workflow runs:

- npm ci
- frontend production build
- real Docker Compose stack
- seeded V0.1 -> V0.2 migration verification
- scripts/smoke_test.py workflow
- mocked backend AI planner tests
- MySQL restart
- persistence verification

Keep coverage for authorization, team-wide visibility, parent/child structure, direct assignment, owner claiming, duplicate-claim prevention, open collaboration, safe unclaim, disabled-member blocking and migration compatibility.

## Production data cleanup

Never delete production test data automatically in migrations or startup code.

Any cleanup of fictional production members/tasks must be a separate reviewed operation that preserves the real administrator and schema, uses explicit identifiers, takes a backup and runs only after user confirmation.
