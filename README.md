# TARS-Go Platform

An open-source operations and collaboration platform for university robotics teams.

V0.1 implements one real workflow:

~~~
administrator creates member
-> copies one-time invitation link
-> member sets password
-> member logs in
-> administrator assigns a task
-> owner/collaborators see the task
-> task owner updates its status
~~~

No public registration, email delivery, OAuth, activity module, notification system, file system, weekly reports, or approval workflow is included.

## Stack

- Vue 3 + TypeScript + Vite
- FastAPI
- SQLAlchemy + PyMySQL
- Alembic
- MySQL 8.4 LTS
- Caddy
- Docker Compose

## Run

~~~
cp .env.example .env
docker compose up -d --build
~~~

Open http://localhost.

For local HTTP, keep SESSION_COOKIE_SECURE=false. For a real HTTPS domain, set APP_DOMAIN to the domain and SESSION_COOKIE_SECURE=true.

Caddy is the only public entry point. /api/* is proxied to FastAPI and every other route serves the Vue SPA.

## Create the first administrator

There is no public registration route. After first deployment:

~~~
docker compose exec api python -m app.bootstrap_admin
~~~

The administrator can then log in at /login, create members, and copy invitation links through member management.

## V0.1 pages

- /login — email/password login
- /invite/:token — one-time password setup
- / — personal work dashboard
- /tasks — tasks related to the current member
- /me — account and management entry
- /admin/members — member invitations and disabling
- /admin/tasks — task creation and editing

The application is mobile-first. The same pages expand naturally on larger screens; there is no separate desktop admin UI.

## Authentication

Passwords are hashed with Argon2 through pwdlib.

Authentication uses an opaque random HttpOnly cookie:

- the raw session token exists only in the browser cookie
- the database stores only SHA-256 hashes of session tokens
- sessions expire after seven days
- disabling a member deletes that member's active sessions
- logout deletes the current session

Invitation tokens follow the same raw-token/hash boundary. They expire after seven days and the invitation row is deleted immediately after activation.

admin and manager can use the current management endpoints. manager is retained as a system role but does not have a separate permission matrix in V0.1.

## Data model

V0.1 uses these tables:

- members — name, email, password hash, role, status, created time
- invitations — one active hashed invitation token per invited member
- sessions — hashed login sessions
- tasks — title, deliverable, owner, deadline, status, creator
- task_collaborators — normal many-to-many task/member association

Member status is invited, active, or disabled.

Task status is todo, doing, or done.

Task deadlines are currently stored as the local wall-clock value entered by the user. V0.1 does not implement multi-timezone conversion.

## Database migrations

The API container runs alembic upgrade head before starting FastAPI. Database structure changes must be added as Alembic migrations instead of being created ad hoc at application startup.

## Development

Frontend:

~~~
cd frontend
npm install
npm run dev
~~~

The Vite server proxies /api to http://127.0.0.1:8000.

Backend development requires MySQL and the DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD and SESSION_COOKIE_SECURE environment variables.

~~~
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
~~~

## Validation

The GitHub Actions workflow builds the real Docker Compose stack and verifies:

- unauthenticated access is rejected
- administrator login
- member invitation and activation
- invitation invalidation after use
- normal members cannot access management endpoints
- task creation with one owner and multiple collaborators
- owner and collaborator task visibility
- only the owner can update a member-owned task
- task status updates
- MySQL restart persistence
- the browser-facing Caddy -> FastAPI -> MySQL path

All test identities are fictional. Runtime passwords are generated inside CI and are not committed.

## Data boundary

The repository is public code. Production data is private.

Never commit .env, passwords, credentials, tokens, private keys, server secrets, database backups, real member data, private team documents, or operational records.

## Structure

~~~
.
├── backend/
│   ├── alembic/
│   ├── app/
│   │   ├── routers/
│   │   ├── auth.py
│   │   ├── bootstrap_admin.py
│   │   ├── db.py
│   │   ├── main.py
│   │   ├── models.py
│   │   └── schemas.py
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   ├── Caddyfile
│   └── Dockerfile
├── scripts/
│   └── smoke_test.py
├── compose.yaml
└── README.md
~~~

## License

MIT
