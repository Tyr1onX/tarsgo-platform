# TARS-Go Platform

An open-source operations and collaboration platform for university robotics teams.

The project is currently in its initial infrastructure stage. The first runnable version provides a Vue frontend, a FastAPI backend, MySQL, and a Caddy entry point managed with Docker Compose.

## Stack

- Vue 3 + TypeScript + Vite
- FastAPI
- SQLAlchemy + PyMySQL
- MySQL 8.4 LTS
- Caddy
- Docker Compose

## Run with Docker

```bash
cp .env.example .env
docker compose up -d --build
```

Then open `http://localhost`.

The home page checks `/api/health`; a healthy response confirms that the frontend, reverse proxy, backend, and database are connected.

## Development

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Backend requires a MySQL-compatible `DATABASE_URL`:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL='mysql+pymysql://tarsgo:change-me@127.0.0.1:3306/tarsgo'
uvicorn app.main:app --reload
```

For normal local integration testing, Docker Compose is the shortest path.

## Structure

```text
.
├── backend/        # FastAPI API
├── frontend/       # Vue app and Caddy image
├── compose.yaml    # Single-server deployment
├── .env.example
└── README.md
```

## Deployment

For a public server, set `APP_DOMAIN` in `.env` to the real domain and point its DNS record to the server. Caddy will serve the frontend and proxy `/api/*` to FastAPI.

Do not commit production secrets, database data, member information, student numbers, phone numbers, leave records, or internal team documents.

## Current scope

Only the application foundation is implemented. Member, activity, task, attendance, leave, and weekly-report modules will be added from real usage requirements rather than pre-built speculatively.

## License

MIT
