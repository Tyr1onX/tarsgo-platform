# AGENTS.md

## Project goal

TARS-Go Platform is an open-source operations and collaboration platform for university robotics teams.

Build only what is required by real team workflows. Keep the system small, understandable, and deployable on one server.

## Working rules

1. Read current code before making architectural decisions. README is supporting documentation, not the source of truth.
2. Prefer the smallest implementation that completes the real workflow.
3. Keep one implementation path and one source of truth for each state.
4. Do not add abstractions, dependencies, services, configuration, or compatibility layers without a current requirement.
5. Fix root causes instead of layering patches.
6. Remove obsolete code when a new implementation replaces it.
7. Keep changes scoped to the current requirement.
8. Never commit production secrets or real private team/member data.

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

Do not introduce Redis, queues, microservices, Kubernetes, a separate API gateway, multiple databases, or deployment control panels without a demonstrated requirement.

## Current stack

- Vue 3 + TypeScript + Vite
- FastAPI
- SQLAlchemy + PyMySQL
- Alembic
- MySQL 8.4 LTS
- Caddy
- Docker Compose

Frontend dependencies are locked with `package-lock.json`; Docker and CI use `npm ci`.

## Current V0.1 scope

~~~text
admin creates member
-> one-time invitation link
-> member sets password
-> member logs in
-> admin/manager creates task
-> owner/collaborators see task
-> owner updates task status
~~~

Do not add activities, leave, weekly reports, notifications, files, AI, GitHub sync, organization editors, points, approval flows, or other business modules unless a later requirement explicitly asks for them.

## Authorization boundary

System roles are `admin`, `manager`, and `member`.

- `admin`: member account management + task management
- `manager`: task management only
- `member`: own related tasks; only a task owner may update its status

Only `admin` may list full member account data, create invitations, regenerate invitations, disable/enable accounts, or create accounts with any system role.

Do not expand member-account endpoints back to `manager`. Use `require_admin` for account management and `require_manager` for admin/manager task-management operations.

Task management needs only a minimal active-member assignment list (id + name). Do not grant managers full member-account reads merely to populate task assignment controls.

Real-world titles such as captain, vice captain, group leader, or project manager are not system roles and must not appear in authorization logic.

## Authentication and member state

Passwords use Argon2 through `pwdlib`.

Login uses a random opaque HttpOnly cookie with SameSite=Lax. Only SHA-256 session-token hashes are stored in MySQL. Production HTTPS requires Secure cookies.

Invitation tokens are random opaque values; only their hashes are stored. They expire after seven days and are removed immediately after activation.

Member states are `invited`, `active`, and `disabled`.

Only active accounts may be disabled. Disabling deletes existing sessions immediately. Enabling restores only a previously active account: it keeps the password, creates no session, and the user must log in again. Do not enable an invited account; the enable path also requires an existing password hash so legacy disabled invitations cannot become active accidentally.

## Current data model

Real V0.1 tables are `members`, `invitations`, `sessions`, `tasks`, `task_collaborators`, and `alembic_version`.

A task has exactly one owner and zero or more collaborators through `task_collaborators`. Do not store collaborator IDs in JSON or strings.

Task status is `todo`, `doing`, or `done`.

Task deadlines are local wall-clock DATETIME values from the current form. Do not introduce partial timezone conversion.

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
    ├── auth.py
    ├── invitations.py
    ├── members.py
    └── tasks.py
~~~

Do not add controller/service/repository/facade layers without a concrete boundary that needs them.

## Frontend boundaries

The frontend intentionally has no UI framework, router library, or state-management library.

Current routes are `/login`, `/invite/:token`, `/`, `/tasks`, `/me`, `/admin/members`, and `/admin/tasks`.

Mobile is the primary layout. PC uses the same responsive UI.

Do not redesign the UI or split `App.vue` only for stylistic reasons. Do not add dashboard statistics, fake buttons, decorative cards, or explanatory content that does not affect the user's next action.

## Public data boundary

Never commit `.env`, passwords, tokens, API keys, private keys, server IPs, database files/backups, real personal information, private team notes, or internal operational records.

Use fictional data for tests and documentation. CI passwords must be generated at runtime.

Git commit author metadata is outside the repository file-content boundary; do not rewrite history to hide it.

## Validation

The V0.1 GitHub Actions workflow runs `npm ci`, the frontend production build, the real Docker Compose stack, and `scripts/smoke_test.py`.

A change is not complete until the relevant validation passes. Keep coverage for unauthenticated access, invitations, admin-only account management, manager task management, member task restrictions, disable/enable session behavior, and database restart persistence.
