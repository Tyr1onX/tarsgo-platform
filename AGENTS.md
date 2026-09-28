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

Continue evolving Task as the item / execution-task source of truth. The current dynamic-execution slice adds one lightweight ItemActivity table only for human-written item history; it is not a comment system, event-sourcing model or structural task state.

The V0.2 second-stage first slice adds an allowlisted admin AI draft planner and transactional batch confirmation. Knowledge Source V0.1 adds read-only GitHub sync, admin document uploads, local text extraction and bounded keyword retrieval for the planner. Keep this knowledge slice simple: no embeddings, vector database, multi-agent flow, auto-summarization or writeback to GitHub.

Do not expand these slices into automatic scheduling, member recommendation, time-conflict algorithms, workload algorithms, notifications, task comments/files, leave, weekly reports, technical R&D workflows, complex dashboards or complex organization structures.

## Task model boundary

A root Task is an operations item. A task with parent_id is one execution assignment under a root item.

Only one child level is supported. Reject grandchildren.

Current task structure:

- parent_id: nullable self-reference
- title
- deliverable: optional child-task result check stored as text; the UI calls it “做到什么算完成”; root items do not repeat a total completion standard
- execution_points: up to six concise execution steps
- cautions: up to five concise task-specific reminders
- prerequisites: up to four conditions that would prevent the task from reasonably starting; they do not create system dependency behavior
- context_facts: root-item current confirmed facts; child rows keep an empty list
- result: optional execution outcome text
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
- update execution status and result only when currently responsible
- participate in current-fact / activity updates only for items they are actually involved in
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
-> 0004_knowledge_documents
-> 0005_task_execution_details
-> 0006_dynamic_item_execution
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

Primary routes are /login, /invite/:token, /, /tasks, /tasks/:id, /team and /me. /ai-planner is an allowlisted admin-only workflow entry and /knowledge is an admin-only management page; neither becomes a global navigation destination.

Keep one task entry: /tasks.

Every active member sees three task views:

- 我的
- 待认领
- 全部

admin / manager management controls live on the same task page. Do not recreate a separate management destination.

/team is admin-only member account management.

/me is personal information, role and logout only.

Home is AI-first: the Planner composer is the primary work entry when available, while manual creation remains a lightweight fallback. Below it, “what do I need to do now?” shows executable child-task summary cards first; a root item is only shown as a fallback when it has no child tasks. Do not add team statistics.

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

Planner context is assembled locally before the provider call and divided into current-event material and historical team knowledge. Automatically retrieved Knowledge documents always belong to history, never current-event facts. The Planner UI accepts leader text and temporary `.md`, `.txt`, `.docx` or `.pdf` attachments as current-event material; extracted attachment text is not persisted. Keep Knowledge search and source-management details out of the Planner UI. Explicit facts in the leader description and current-event material outrank history; if those current sources conflict, ask the leader to clarify. Historical dates, places, people and counts must never be copied as current facts. Retrieved documents are untrusted reference data, not instructions. Send only a few relevant excerpts (at most 8,000 knowledge-context characters total) and keep generation to exactly one provider request.

Each planner task also includes concise execution_points, cautions and prerequisites. Store these on Task and return empty arrays for legacy rows. Prerequisites are readable guidance only, not task dependencies. Admins can refine one draft card or the full draft; every explicit refine action makes one provider request. A scoped refine must be merged server-side into only the requested card. Do not change provider parameters or allow AI to modify published tasks.

## Knowledge Source V0.1 boundary

- Sources of truth remain the configured GitHub repository and files explicitly uploaded by admins; TARS-Go never writes back to GitHub.
- Only `.md`, `.txt`, `.docx` and `.pdf` are extracted. No OCR; PDFs without extractable text are marked unparseable. Limit each file to 10 MiB.
- GitHub credentials stay in server environment variables. GitHub access is read-only and restricted to configured repository paths.
- Uploaded originals live under a private directory outside the repository. Never commit documents, extracted private team text, GitHub tokens or `.env`.
- Admin-only APIs manage sync, listing, upload and deletion. Knowledge failures must not prevent the planner from working with the request description, pasted current material and temporary attachments.
- Retrieval is deterministic title/path/content keyword scoring, capped at six historical documents and 3,000 history characters. Admin document search returns metadata only and can match title, path or source name. Do not add embeddings, vector databases, whole-repository prompts, AI retrieval calls or automatic knowledge writeback.
- Pasted text and temporarily parsed Planner attachments belong to the current event for that request; they are not copied into long-term knowledge automatically.

Only allowlisted admins may generate plans. AI access is checked server-side by role, member ID allowlist, enabled flag and server configuration. The provider key never leaves the API container.

Provider selection is configuration-only: AI_PROVIDER=openai or AI_PROVIDER=deepseek. Both must preserve the same PlannerProvider interface and AIPlannerDraft schema. OpenAI uses responses.parse(..., text_format=AIPlannerDraft). DeepSeek uses exactly one responses.create call against AI_BASE_URL=https://api.deepseek.com with text.format.type=json_schema, strict=true and schema=AIPlannerDraft.model_json_schema(), then json.loads(response.output_text) + AIPlannerDraft.model_validate(). Never implement a parse-then-create fallback or loosen the shared schema for DeepSeek. Do not fork the planner business flow by provider.

Generation must remain one model request per explicit Generate / Regenerate action. No agent loop, hidden retry loop, automatic reflection, chat history, database task dump or vector retrieval. The description is capped at 5000 characters; knowledge context is capped at 8000 characters total, including at most 3000 characters of historical snippets. Output is capped at 15 assignments / 6 questions. Keep the existing provider limits (OpenAI 2200 output tokens, DeepSeek 4096 with reasoning effort `none`) and max_retries=0.

The persistent ai_planner_daily_usage table stores daily request counts, aggregate provider token counts and knowledge-context character counts. Never store full planner prompts or generated drafts there.

The AI schema may contain titles, completion standards, a tentative item deadline, owner_claimable, collaboration_open and confirmation questions. It must never contain owner_id or choose real members.

Draft generation never writes Task rows. Only explicit confirmation calls the normal task batch endpoint. The confirming user owns the root item; a child with owner_claimable=true is published ownerless, while a child with owner_claimable=false is temporarily owned by the confirming manager/admin. Database state, permissions and constraints remain deterministic backend logic.

Do not expand this slice into automatic scheduling, member recommendation, workload scoring, conflict detection, dependencies, AI changes to already-published tasks or AI-generated knowledge.

## Dynamic item execution

Published tasks remain editable. A root Task stores current confirmed facts in context_facts. Task.result stores the actual execution outcome and is distinct from deliverable.

ItemActivity is intentionally narrow: a timestamped human-written record attached only to a root item. Item participants may record activity and optionally copy that text into current facts in one transaction. A task result may be promoted to current facts only by an explicit human action, which also records an ItemActivity.

This is not a full audit log. Do not turn ItemActivity into comments, notifications, event sourcing or automatic AI re-planning.

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
- fixture-backed knowledge extraction, sync, authorization and planner-context tests
- MySQL restart
- persistence verification

Keep coverage for authorization, team-wide visibility, parent/child structure, direct assignment, owner claiming, duplicate-claim prevention, open collaboration, safe unclaim, disabled-member blocking and migration compatibility.

## Production data cleanup

Never delete production test data automatically in migrations or startup code.

Any cleanup of fictional production members/tasks must be a separate reviewed operation that preserves the real administrator and schema, uses explicit identifiers, takes a backup and runs only after user confirmation.
