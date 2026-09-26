# AGENTS.md

## Project goal

TARS-Go Platform is an open-source operations and collaboration platform for university robotics teams.

Build only what is required by real team workflows. The system should remain small, understandable, and deployable on a single server.

## Working rules

1. Read the current code before making architectural decisions. README is supporting documentation, not the source of truth.
2. Prefer the smallest implementation that completes the real workflow.
3. Keep one implementation path and one source of truth for each state.
4. Do not add abstractions, dependencies, services, configuration, or compatibility layers without a current requirement.
5. Fix root causes instead of adding defensive patches.
6. Remove obsolete code when a new implementation fully replaces it.
7. Keep changes scoped to the current requirement; do not perform unrelated large refactors.
8. Verify third-party behavior against the current version before relying on it.
9. Never commit production secrets or real private team/member data.

## Architecture

~~~
Browser
  |
Caddy
  |-- Vue static frontend
  |
  +-- /api/* -> FastAPI -> MySQL
~~~

The deployment target is a single VPS using Docker Compose. The API container runs Alembic migrations before starting FastAPI.

Do not introduce Redis, message queues, microservices, Kubernetes, a separate API gateway, or multiple databases unless the existing architecture is proven insufficient by a real requirement.

## Current stack

- Vue 3 + TypeScript + Vite
- FastAPI
- SQLAlchemy + PyMySQL
- Alembic
- MySQL 8.4 LTS
- Caddy
- Docker Compose

## Current V0.1 workflow

~~~
admin creates member
-> one-time invitation link
-> member sets password
-> member logs in
-> admin creates task
-> owner/collaborators see task
-> owner updates task status
~~~

Do not extend this workflow with activities, leave, weekly reports, notifications, files, AI, GitHub sync, organization editors, points, or approval flows unless a later task explicitly requires them.

## Authentication and authorization

System roles are admin, manager and member.

admin and manager currently share the management boundary. Do not add a permission matrix until a real manager-specific requirement exists.

Passwords use Argon2 through pwdlib.

Login uses an opaque random HttpOnly cookie. Only the SHA-256 hash of the session token is stored in MySQL. Do not replace this with browser-readable tokens, JWT refresh-token infrastructure, or OAuth without a demonstrated requirement.

Invitation tokens are also random opaque values with only their hashes stored in MySQL. One invited member has at most one current invitation row. Accepting the invitation deletes that row immediately.

## Current data model

The real V0.1 tables are members, invitations, sessions, tasks, task_collaborators and alembic_version.

Member status is invited, active, or disabled. Task status is todo, doing, or done.

A task has exactly one owner and zero or more collaborators through task_collaborators. Do not store collaborator IDs in JSON or string fields.

Task deadlines are currently local wall-clock DATETIME values from the user form. Do not introduce UTC conversion in only one layer; timezone support must be designed end to end if it becomes a real requirement.

## Backend boundaries

~~~
app/
├── auth.py
├── bootstrap_admin.py
├── db.py
├── main.py
├── models.py
├── schemas.py
└── routers/
    ├── auth.py
    ├── invitations.py
    ├── members.py
    └── tasks.py
~~~

Do not add controller/service/repository/facade layers around these modules without a concrete boundary that needs them.

## Frontend boundaries

The frontend intentionally has no UI framework and no separate desktop application.

Current routes are /login, /invite/:token, /, /tasks, /me, /admin/members and /admin/tasks.

Mobile is the primary layout. PC is the same UI with responsive expansion.

Do not add dashboard statistics, decorative cards, fake buttons, unused routes, or explanatory UI that does not change the user's next action.

## Data boundary

The repository is public. Production data is private.

Never commit .env, credentials, passwords, tokens, private keys, server secrets, database files, backups, real personal information, leave/attendance records, private meeting notes, or internal team documents.

Use fictional data for tests and documentation. CI secrets and passwords must be generated at runtime.

## Validation

The V0.1 GitHub Actions workflow builds the real Docker Compose stack and runs scripts/smoke_test.py.

A change to the current workflow is not complete until the relevant validation passes. The test must keep covering authentication boundaries, invitation invalidation, task owner/collaborator visibility, task status permissions, and database restart persistence.
