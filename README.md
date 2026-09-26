# TARS-Go Platform

TARS-Go is an open-source collaboration platform for university robotics teams.

The current product direction is a **public operations collaboration board** for work such as promotion, event execution, recruitment, materials, livestreaming and photography.

Discussion still happens in WeChat, meetings or offline. TARS-Go records work that has already been clarified and keeps the current execution state visible to the team.

Technical R&D workflows for mechanical, electrical or algorithm teams are not part of the current V0.2 scope.

## Current workflow

~~~text
admin / manager publishes an operations item
-> item may be split into one level of execution tasks over time
-> owner is assigned directly or opened for claiming
-> collaborators are assigned directly or may join when collaboration is open
-> all active members can see published work
-> owners update execution status
-> admin / manager keeps structure and assignments aligned with reality
~~~

See:

- docs/operations-workflow.md — product workflow and task-granularity rules
- docs/ai-direction.md — long-term AI role and explicit boundaries

## Stack

- Vue 3 + TypeScript + Vite
- FastAPI
- SQLAlchemy + PyMySQL
- Alembic
- MySQL 8.4 LTS
- Caddy
- Docker Compose

## Permissions

System roles are independent from real-world team titles.

### admin

- manage member accounts
- create, edit and reassign all operations items and execution tasks
- use the same claiming / collaboration actions available to active members

### manager

- create, edit and reassign all operations items and execution tasks
- read the minimal active-member list required for assignment
- no member-account administration

### member

- view all published operations work
- view work they own or collaborate on
- view currently claimable work
- claim an ownerless task when owner claiming is open
- cancel their own claim when the task is not completed and remains claimable
- join / leave open collaboration
- update status only for tasks they currently own

Backend authorization is the security boundary.

## Task model

V0.2 continues to use the existing tasks table rather than adding an Activity model.

A task may be:

- a root item (parent_id = NULL) representing an operations item
- a one-level child task (parent_id = root task id) representing an execution assignment

Current task fields include:

- title
- optional completion standard (deliverable)
- optional owner
- owner_claimable
- collaborators
- collaboration_open
- parent id
- explicit deadline
- status: todo | doing | done

A published task must either have an owner or allow owner claiming.

Only one child level is supported in V0.2. Grandchildren are rejected.

Historical tasks may continue to reference disabled members. Existing assignments are not revalidated during unrelated edits; newly submitted owners and collaborators must be active.

## Pages

- /login — email/password login
- /invite/:token — one-time password setup
- / — “what do I need to do now?” home view
- /tasks — single task entry for every role
- /team — admin-only member account management
- /me — personal information, system role and logout

/tasks provides three views to every active member:

- **我的** — tasks the member owns or collaborates on
- **待认领** — ownerless, non-completed tasks with public owner claiming enabled
- **全部** — all published operations items and execution tasks

admin / manager can open a lightweight form from the same task page to create a root item or add one execution task below an item.

Legacy /admin/tasks redirects to /tasks, and /admin/members redirects to /team.

## Claiming and collaboration

Owner claiming is atomic at the database update boundary: once one member claims an ownerless task, a second claimant receives a conflict instead of overwriting the owner.

A member may cancel their own claim only when:

- they are the current owner
- the task is not done
- the task is still marked as owner-claimable

Open collaboration allows active non-owners to join or leave themselves while the task is not completed.

admin / manager may always reassign owners and collaborators through normal task editing.

## Authentication and member lifecycle

Passwords are hashed with Argon2 through pwdlib.

Login uses an opaque random HttpOnly cookie:

- only the cookie contains the raw session token
- MySQL stores only SHA-256 token hashes
- SameSite is Lax
- production HTTPS must use SESSION_COOKIE_SECURE=true
- sessions expire after seven days
- disabling an account deletes all sessions immediately

Invitation tokens are opaque random values; only their hashes are stored. Invitations expire after seven days and are deleted after activation.

Member states are invited, active and disabled.

Only active accounts can use task claiming or collaboration APIs because every action requires a valid active session.

## Database migration

V0.2 adds Alembic revision:

~~~text
0002_operations_claiming
~~~

It upgrades the existing V0.1 tasks table without deleting data:

- existing owner_id values are preserved
- owner_id becomes nullable
- parent_id is added nullable
- owner_claimable defaults to false
- collaboration_open defaults to false
- existing completion standards and statuses remain unchanged

CI includes a real 0001_v0_1 -> 0002_operations_claiming compatibility check using seeded legacy data.

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

The API container runs alembic upgrade head before FastAPI starts.

## Create the first administrator

There is no public registration route.

~~~bash
docker compose exec api python -m app.bootstrap_admin
~~~

The first administrator can invite remaining accounts from /team.

## Frontend development

Dependencies are locked with package-lock.json.

~~~bash
cd frontend
npm ci
npm run build
npm run dev
~~~

## RackNerd deployment preparation

For a single VPS behind an existing Nginx server:

~~~text
APP_DOMAIN=your-domain.example
CADDY_SITE_ADDRESS=:80
WEB_BIND_ADDRESS=127.0.0.1
WEB_HTTP_PORT=8080
SESSION_COOKIE_SECURE=true

MYSQL_DATABASE=tarsgo
MYSQL_USER=tarsgo
MYSQL_PASSWORD=<strong-random-password>
MYSQL_ROOT_PASSWORD=<strong-random-password>
~~~

Then:

~~~bash
docker compose up -d --build
~~~

Only the web container's HTTP port is published. FastAPI and MySQL remain on the internal Docker network. MySQL data stays in the named mysql_data volume.

## Validation

GitHub Actions runs:

~~~bash
cd frontend
npm ci
npm run build
~~~

and:

~~~bash
docker compose up -d --build
python scripts/smoke_test.py workflow http://127.0.0.1
python scripts/smoke_test.py persistence http://127.0.0.1
~~~

Coverage includes:

- member visibility of all published operations tasks
- parent / child correctness and one-level limit
- direct assignment and public owner claiming
- atomic prevention of duplicate claiming
- open collaboration join / leave
- safe claim cancellation
- admin / manager reassignment
- member structural-edit restrictions
- owner-only member status updates
- disabled-member blocking
- database restart persistence
- V0.1 legacy-data migration

## Deliberately deferred

V0.2 first stage does **not** implement:

- AI API / LLM provider
- automatic scheduling
- time-conflict calculation
- task recommendation algorithms
- workload algorithms
- notifications
- comments
- files
- leave
- weekly reports
- technical R&D management
- complex dashboards
- complex organization structures
- full field-change history

The product direction for later AI and richer execution metadata is documented, but not implemented yet.

## Public repository boundary

This repository is public. Never commit:

- .env
- passwords, credentials, session tokens, invite tokens, API keys or private keys
- VPS IP addresses or other private server details
- database files or backups
- real member names, email addresses, student numbers, phone numbers or internal team material

Tests and documentation use fictional identities such as 张三, 李四, admin@example.com and lisi@example.com.

Contributors who do not want their personal Git email exposed in commit metadata should configure a GitHub-provided noreply address before committing. Existing Git history is not rewritten.

## Production test-data cleanup

Do not delete production data automatically through migrations or application startup.

After V0.2 deployment, cleanup of fictional production test data should be a separately reviewed database operation that:

1. identifies fictional accounts and tasks by explicit IDs / emails / titles
2. preserves the database schema and Alembic version
3. preserves the real administrator account
4. deletes dependent task-collaborator rows, tasks, sessions and invitations before deleting fictional members
5. runs inside a transaction after a backup
6. is reviewed before execution

No production cleanup is executed by this release.

## License

MIT
