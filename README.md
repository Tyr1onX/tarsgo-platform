# TARS-Go Platform

An open-source operations and collaboration platform for university robotics teams.

The project is currently at its infrastructure stage. The runnable foundation contains a Vue frontend, a FastAPI backend, MySQL, and Caddy, managed by one Docker Compose file.

## Stack

- Vue 3 + TypeScript + Vite
- FastAPI
- SQLAlchemy + PyMySQL
- MySQL 8.4 LTS
- Caddy
- Docker Compose

## Run

```bash
cp .env.example .env
docker compose up -d --build
```

Open `http://localhost`.

The home page requests `/api/health`. A healthy result confirms that the browser-facing frontend, Caddy reverse proxy, FastAPI service, and MySQL connection are all working.

## Development

For the full local stack, Docker Compose is the shortest path.

Frontend-only development:

```bash
cd frontend
npm install
npm run dev
```

The Vite development server proxies `/api` to `http://127.0.0.1:8000`.

Backend development requires MySQL and these environment variables:

```bash
export DB_HOST=127.0.0.1
export DB_PORT=3306
export DB_NAME=tarsgo
export DB_USER=tarsgo
export DB_PASSWORD=change-me

cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Structure

```text
.
├── backend/
│   ├── app/
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   ├── Caddyfile
│   ├── Dockerfile
│   └── package.json
├── compose.yaml
├── .env.example
└── README.md
```

## RackNerd deployment

1. Point a domain's DNS record to the VPS.
2. Copy `.env.example` to `.env`.
3. Set `APP_DOMAIN` to the real domain.
4. Replace every example database password.
5. Run `docker compose up -d --build`.

Only ports 80 and 443 are published by Compose. MySQL and FastAPI remain on the internal Docker network. Caddy handles the public entry point and HTTPS when `APP_DOMAIN` is a real domain.

## Data boundary

The repository is public code. Production data is private.

Never commit:

- `.env` or credentials
- database files or backups
- real names, student numbers, phone numbers, or other member data
- leave and attendance records
- internal meeting notes or private team documents

## Current scope

Only the application foundation is implemented. Member, activity, task, attendance, leave, and weekly-report modules will be added from actual team workflows instead of being pre-built speculatively.

## License

MIT
