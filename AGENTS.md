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

Keep the current deployment model unless a real limitation appears:

```text
Browser
  |
Caddy
  |-- Vue static frontend
  |
  +-- /api/* -> FastAPI -> MySQL
```

The deployment target is a single VPS using Docker Compose.

Do not introduce Redis, message queues, microservices, Kubernetes, a separate API gateway, or multiple databases unless the existing architecture is proven insufficient by a real requirement.

## Current stack

- Vue 3 + TypeScript + Vite
- FastAPI
- SQLAlchemy + PyMySQL
- MySQL 8.4 LTS
- Caddy
- Docker Compose

## Product scope

The foundation is implemented first. Business modules should be added from actual usage.

Current expected order:

1. members
2. activities
3. tasks
4. attendance / leave
5. weekly reports / activity reviews

Do not pre-build speculative modules such as chat, forums, complex approval engines, generic workflow builders, file drives, or multi-tenant billing.

## Data boundary

The repository is public. Production data is private.

Never commit:

- `.env`
- credentials, tokens, private keys, or server secrets
- database files or backups
- real names, student numbers, phone numbers, or other personal information
- leave/attendance records
- private meeting notes or internal team documents

Use fictional demo data for development and documentation.

## Validation

For code changes, verify the smallest relevant workflow before considering the change complete. For infrastructure changes, verify Docker Compose and the browser -> Caddy -> FastAPI -> MySQL path.
