# TARS-Go Platform

An open-source operations and collaboration platform for university robotics teams.

V0.1 is intentionally limited to one workflow:

~~~text
admin creates member
-> copies one-time invitation link
-> member sets password
-> member logs in
-> admin/manager assigns a task
-> owner/collaborators see the task
-> task owner updates its status
~~~

No public registration, email delivery, OAuth, activity module, leave, weekly reports, notifications, files, AI, organization editor, or approval workflow is included.

## Stack

- Vue 3 + TypeScript + Vite
- FastAPI
- SQLAlchemy + PyMySQL
- Alembic
- MySQL 8.4 LTS
- Caddy
- Docker Compose

## Permissions

System roles are deliberately separate from real team titles.

- `admin`
  - member account management
  - create invitations for admin / manager / member
  - regenerate pending invitations
  - disable and enable active accounts
  - full task management
- `manager`
  - view all tasks
  - create and modify tasks
  - read the minimal active-member list required for task assignment
  - no member account management
- `member`
  - view tasks where they are the owner or collaborator
  - update status only when they are the task owner

The backend is the security boundary. Hiding frontend controls is not treated as authorization.

## Run locally

~~~bash
cp .env.example .env
docker compose up -d --build
~~~

Open http://localhost.

For local HTTP:

~~~text
APP_DOMAIN=:80
SESSION_COOKIE_SECURE=false
~~~

The API container runs `alembic upgrade head` before FastAPI starts.

## Create the first administrator

There is no public registration route. After the stack is running:

~~~bash
docker compose exec api python -m app.bootstrap_admin
~~~

The first administrator can then create the remaining accounts from `/admin/members`.

## Frontend development

Frontend dependencies are locked with `package-lock.json`.

~~~bash
cd frontend
npm ci
npm run build
npm run dev
~~~

The Vite development server proxies `/api` to `http://127.0.0.1:8000`.

## V0.1 pages

- `/login` — email/password login
- `/invite/:token` — one-time password setup
- `/` — personal work dashboard
- `/tasks` — current member's related tasks
- `/me` — account and permitted management entries
- `/admin/members` — admin-only member account management
- `/admin/tasks` — admin/manager task management

The application is mobile-first and uses the same responsive UI on desktop.

## Authentication and member lifecycle

Passwords are hashed with Argon2 through `pwdlib`.

Login uses an opaque random HttpOnly cookie:

- only the cookie contains the raw session token
- MySQL stores only SHA-256 token hashes
- SameSite is `Lax`
- production HTTPS must use `SESSION_COOKIE_SECURE=true`
- sessions expire after seven days
- logout removes the current session
- disabling an account deletes all of that account's sessions immediately

Invitation tokens are also opaque random values. MySQL stores only their hashes. Invitations expire after seven days and are deleted immediately after successful activation.

Member states are:

- `invited` — password has not been set
- `active` — account can log in
- `disabled` — previously active account is blocked

Only an `active` account can be disabled. Enabling restores a previously active disabled account to `active`, keeps the existing password, creates no session, and requires the member to log in again. Pending `invited` accounts are not enabled through the restore endpoint. The restore endpoint also refuses legacy disabled rows that have no password hash.

## Data model

V0.1 uses:

- `members`
- `invitations`
- `sessions`
- `tasks`
- `task_collaborators`
- `alembic_version`

A task has exactly one owner and zero or more collaborators through the association table. Task status is `todo`, `doing`, or `done`.

Historical tasks may continue to reference members who were later disabled. Editing title, deliverable, deadline, or status does not revalidate existing assignments. Any newly submitted owner or collaborator assignment must reference an active member.

Task deadlines are stored as the local wall-clock value entered by the user. V0.1 does not implement multi-timezone conversion.

## RackNerd deployment preparation

For a single VPS, create a production `.env` with values similar to:

~~~text
APP_DOMAIN=your-domain.example
SESSION_COOKIE_SECURE=true

MYSQL_DATABASE=tarsgo
MYSQL_USER=tarsgo
MYSQL_PASSWORD=<strong-random-password>
MYSQL_ROOT_PASSWORD=<strong-random-password>
~~~

Then run:

~~~bash
docker compose up -d --build
~~~

The current Compose topology intentionally exposes only Caddy ports 80/443. FastAPI and MySQL remain on the internal Docker network. MySQL uses the named `mysql_data` volume, and Caddy keeps its data/config volumes for HTTPS operation.

Point the domain's DNS records at the VPS before relying on Caddy's automatic HTTPS.

## Validation

GitHub Actions runs both:

~~~bash
cd frontend
npm ci
npm run build
~~~

and the real:

~~~bash
docker compose up -d --build
~~~

The Compose smoke test covers authentication, invitation invalidation, admin/manager/member permission boundaries, manager task management, member disable/enable behavior, immediate session invalidation, task owner/collaborator permissions, and MySQL restart persistence.

## Public repository boundary

This repository is public. Never commit:

- `.env`
- passwords, credentials, session tokens, invite tokens, API keys, or private keys
- VPS IP addresses or other private server details
- database files or backups
- real member names, email addresses, student numbers, phone numbers, or internal team material

Tests and documentation use fictional identities such as 张三, 李四, `admin@example.com`, and `lisi@example.com`.

Contributors who do not want their personal Git email exposed in commit metadata should configure a GitHub-provided `noreply` address before committing. Existing Git history is not rewritten for this purpose.

## License

MIT
