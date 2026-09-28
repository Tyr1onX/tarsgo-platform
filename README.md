# TARS-Go Platform

TARS-Go is an open-source collaboration platform for university robotics teams.

The current product direction is a **public operations collaboration board** for work such as promotion, event execution, recruitment, materials, livestreaming and photography.

Discussion still happens in WeChat, meetings or offline. TARS-Go records work that has already been clarified and keeps the current execution state visible to the team.

Technical R&D workflows for mechanical, electrical or algorithm teams are not part of the current V0.2 scope.

## Current workflow

~~~text
admin may optionally turn a natural-language requirement into an editable AI draft
-> human edits / deletes / adds draft assignments
-> confirmation atomically creates one operations item plus first-level assignments
-> admin / manager may also publish an operations item manually
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
- optional child-task result check (“做到什么算完成”; root items do not repeat a total completion standard)
- execution points (up to 6 short strings)
- cautions (up to 5 short strings)
- prerequisites (up to 4 short strings; only conditions that would prevent the task from reasonably starting, with no system dependency behavior)
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
- /ai-planner — allowlisted admin-only AI planning workspace; not global navigation
- /knowledge — admin-only GitHub and document knowledge management; visible in the desktop main navigation
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

## AI planner

V0.2 second-stage first slice implements a small planning flow:

~~~text
natural-language requirement
-> one structured AI draft
-> human edits / removes / adds draft assignments
-> deterministic backend validation
-> explicit confirmation
-> one root item + first-level assignments in one transaction
~~~

The planner is not a chatbot and never writes tasks during generation. It cannot return member IDs or assign real members.

Access requires all of:

- active authenticated user
- system role admin
- member ID listed in AI_PLANNER_ALLOWED_MEMBER_IDS
- AI_PLANNER_ENABLED=true
- server-side AI_API_KEY and AI_MODEL

The frontend only shows the entry when /api/ai/planner/access says it is available. The planner POST endpoint performs the authoritative checks again.

Planner uses a natural-language composer followed by an editable structured draft. Each assignment includes a completion standard, concise execution points, cautions and prerequisites. Prerequisites are readable guidance only, not database dependencies. Admins can use one-card or full-draft natural-language refine; each action makes exactly one SDK model request, and scoped changes are merged into only their target card. It supports `.md`, `.txt`, `.docx` and `.pdf` files up to 10 MiB each; extraction is temporary, does not write to Knowledge, and does not use OCR. The planner automatically searches a bounded set of local Knowledge Source documents in the background, without showing source lists or retrieval controls in the Planner UI. There is no agent loop, automatic reflection, database task dump or vector retrieval. Input description is capped at 5000 characters, current-event material at 5000 characters, knowledge context at 8000 characters, and output at 15 assignments / 6 questions. The official OpenAI Python SDK is configured with automatic retries disabled. A persistent per-member UTC-day counter caps planning and refinement at 20 attempts per day and stores aggregate input/output/total token usage and knowledge-context character counts without storing prompt or draft text.

### AI planner configuration

Production .env adds:

~~~text
AI_PLANNER_ENABLED=true
AI_PLANNER_ALLOWED_MEMBER_IDS=<comma-separated member ids>
AI_PROVIDER=openai
AI_BASE_URL=
AI_API_KEY=<server-side key>
AI_MODEL=<structured-output-capable model>

# DeepSeek:
# AI_PROVIDER=deepseek
# AI_BASE_URL=https://api.deepseek.com
# AI_MODEL=deepseek-flash
~~~

The repository contains only blank / disabled placeholders. The API key is never sent to the frontend or returned by API responses.

Both OpenAI and DeepSeek adapters use the official OpenAI Python SDK. OpenAI keeps using responses.parse(..., text_format=AIPlannerDraft). DeepSeek connects to its official OpenAI-compatible Responses API at https://api.deepseek.com but uses one responses.create request with text.format.type=json_schema, strict=true and AIPlannerDraft.model_json_schema(), then validates response.output_text locally with json.loads() and AIPlannerDraft.model_validate(). There is no parse-then-create fallback, so one Generate action still performs exactly one model request.

## Database migration

Current Alembic chain:

~~~text
0001_v0_1
-> 0002_operations_claiming
-> 0003_ai_planner_usage
-> 0004_knowledge_documents
-> 0005_task_execution_details
~~~

It upgrades the existing V0.1 tasks table without deleting data:

- existing owner_id values are preserved
- owner_id becomes nullable
- parent_id is added nullable
- owner_claimable defaults to false
- collaboration_open defaults to false
- existing completion standards and statuses remain unchanged

CI includes a real 0001_v0_1 -> 0002_operations_claiming compatibility check using seeded legacy data.
The latest migration adds JSON arrays for execution points, cautions and prerequisites, backfilled as empty arrays for existing tasks.

## Knowledge Source V0.1

Admins can sync only configured paths from one configured GitHub repository or upload individual `.md`, `.txt`, `.docx` and `.pdf` files at `/knowledge`. GitHub access is read-only; credentials remain in the server `.env`. Uploaded originals are stored under `/opt/tarsgo-knowledge` by default, outside the repository and in a private directory. Files are limited to 10 MiB. PDFs are text-extracted without OCR; files with no extractable text are marked accordingly.

Extracted text and source metadata are indexed in `knowledge_documents`. GitHub paths are upserted by source path and content hash; missing files are marked removed. Local retrieval scores title, path and text keywords and automatically sends at most six short historical excerpts, with up to 3,000 history characters. The Planner UI does not expose Knowledge source search or history details. Pasted text and temporarily extracted Planner attachments have a separate 5,000-character budget and take precedence; Planner attachments never create Knowledge records or persist to the Knowledge storage directory. Automatically retrieved history is never presented as current-event fact: old dates, places, people and counts must not be applied to the current activity. Documents are treated as untrusted reference text, never as instructions. No embedding, vector database or model-based retrieval is used.

Server-side configuration:

~~~text
KNOWLEDGE_ENABLED=false
KNOWLEDGE_GITHUB_REPO=owner/repository
KNOWLEDGE_GITHUB_BRANCH=main
KNOWLEDGE_GITHUB_TOKEN=<read-only fine-grained token, if required>
KNOWLEDGE_GITHUB_PATHS=docs,knowledge
KNOWLEDGE_STORAGE_HOST_DIR=/opt/tarsgo-knowledge
~~~

For a private repository, use a fine-grained token restricted to that repository with Contents read-only permission. Keep tokens and uploaded/private team material out of Git and ordinary logs. The API never returns document text, server filesystem paths or GitHub credentials.

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
- admin-only knowledge APIs, supported text extraction, file limits, GitHub path/hash sync, removed-source handling and bounded planner retrieval
- one planner provider call and graceful operation when the knowledge index is unavailable
- owner-only member status updates
- disabled-member blocking
- database restart persistence
- V0.1 legacy-data migration
- AI planner admin + allowlist authorization
- missing AI configuration and overlong input
- mocked one-call structured draft generation without task writes
- editable draft confirmation and atomic batch rollback
- persistent AI request/token accounting
- mocked OpenAI parse path and DeepSeek create + json_schema + Pydantic validation path

## Deliberately deferred

V0.2 first stage does **not** implement:

- AI automatic scheduling
- AI member selection / personnel recommendation
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
