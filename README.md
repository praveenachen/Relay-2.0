# Relay

Relay is a student workflow platform that turns information into understanding, a plan, and actions a person explicitly approves.

**Status: Phase 4 LEARN vertical slice implemented.** Relay has real accounts and revocable sessions, saved preferences, workflow drafts, private lecture document ingestion, typed AI summarization, editable approval payloads, local mock execution, external artifact records, encrypted connection infrastructure, and a working onboarding/workspace UI. Real provider OAuth writes, retrieval, scheduling, collaboration automation, and Agent Runtime integration are not implemented.

## Three planned workflows

| Workflow | Planned outcome |
| --- | --- |
| Learn (`lecture_to_notion`) | Lecture notes become structured Notion notes. |
| Plan (`study_scheduler`) | Tasks, calendar availability and preferences become a realistic study schedule. |
| Collaborate (`project_meeting`) | Meeting transcripts become Notion action items and GitHub work. |

The dashboard reads versioned definitions from the API. LEARN accepts PDF, DOCX, Markdown, and plain text source files, parses them locally, generates typed study notes, and runs only after approval. PLAN and COLLABORATE still save drafts only.

## Technical thesis

How do we safely convert probabilistic interpretation into deterministic external actions?

```text
Input -> Understand -> Structure -> Validate -> Propose
  -> Human review -> Approve -> Execute -> Verify
```

Relay decides **what should happen**. The separate Agent Runtime repository will own **how it executes reliably**. Relay owns users, domain planning, approvals, OAuth and connector behavior; Runtime will own queues, retries, timeout handling, idempotency support, execution state and operational telemetry. The typed RuntimeClient remains a Protocol without any implementation or HTTP integration.

## Repository and architecture

```text
frontend/
  app/                     Landing, auth and protected workspace pages
  components/              Reusable forms, cards, navigation and Relay Line
  features/                Auth, runs, definitions, approvals, preferences, connections and LEARN API modules
  hooks/                   TanStack Query server-state hooks
  lib/                     Zod schemas, API transport and server session validation
  tests/                   Playwright browser flows
backend/
  app/api/                 Thin HTTP routes and error mapping
  app/auth/                FastAPI Users configuration and account adapter
  app/domain/              Pure enums, lifecycle rules, errors and ports
  app/models/              SQLAlchemy entities and immutable-record guards
  app/repositories/        Owner-scoped queries and row locks
  app/services/            Transactional workflows, approvals, accounts and audit
  app/infrastructure/      Fernet credential adapter
  app/db/                  SQLAlchemy configuration
  app/runtime/             Runtime contract plus local mock executor adapter
  app/documents/           Private source storage, validation and PDF/DOCX/MD/TXT parsers
  app/workflows/           Workflow-specific orchestration and typed summaries
  alembic/                 Static schema migrations and definition seed
  tests/                   Domain, API, authorization, encryption and concurrency tests
scripts/                   Portable developer commands
.github/workflows/         CI with PostgreSQL and browser tests
docs/                      Architecture, security and ADRs
```

The core domain imports no FastAPI, SQLAlchemy, React, OAuth SDK, or language-model client. API routes return explicit schemas and delegate mutations to services. Async SQLAlchemy sessions support FastAPI Users and application services; synchronous database access is reserved for Alembic/diagnostics. Migrations, not application startup, own schema creation.

Read [system context](docs/architecture/system-context.md), [domain model](docs/architecture/domain-model.md), [workflow state machine](docs/architecture/workflow-state-machine.md), [runtime boundary](docs/architecture/relay-agent-runtime-boundary.md), [LEARN workflow](docs/architecture/learn-workflow.md), and [document processing](docs/architecture/document-processing.md). Design decisions are recorded in [ADRs](docs/decisions).

## Local development

Prerequisites: Python 3.12, Node.js 24 LTS with npm, Docker with Compose v2. GNU Make is optional.

From the repository root:

```sh
python scripts/dev.py setup
python scripts/dev.py dev
```

Setup creates `backend/.venv`, installs pinned dependencies, and copies example environment files without overwriting existing values. Dev starts PostgreSQL, applies migrations (including the three definitions), and runs both applications. Ctrl+C stops the servers. PostgreSQL remains running until `python scripts/dev.py db-down`.

- Relay: http://localhost:3000
- Signup: http://localhost:3000/signup
- API liveness: http://localhost:8000/health
- API docs: http://localhost:8000/docs

Root `.env` configures the API and Compose. `frontend/.env.local` holds `API_INTERNAL_URL` for the Next.js same-origin `/api` proxy. Cookie writes require exactly `FRONTEND_ORIGIN`; use localhost consistently. `COOKIE_SECURE=false` is for local HTTP only. Production must use HTTPS and Secure cookies.

**Upgrading from Phase 0:** add `COOKIE_SECURE=false`, `FRONTEND_ORIGIN=http://localhost:3000`, and `SESSION_LIFETIME_SECONDS=86400` to your existing local `.env` if missing; add `API_INTERNAL_URL=http://127.0.0.1:8000` to the frontend env file. Run setup to update dependencies, then migrate. The setup command preserves existing env files.

No OAuth keys or encryption key are required to sign up and use drafts/preferences. Connection authorization intentionally returns 501. LEARN uses `LANGUAGE_MODEL_PROVIDER=fake` by default for deterministic local summaries. To call OpenAI for typed summaries, set `LANGUAGE_MODEL_PROVIDER=openai`, `OPENAI_API_KEY`, and optionally `OPENAI_MODEL`; responses are requested with schema parsing and `store=false`. Before persisting real provider credentials, configure a generated `TOKEN_ENCRYPTION_KEY` as described in [credential storage](docs/security/credential-storage.md). Never commit real credentials or expose them as `NEXT_PUBLIC_*` settings.

| Make command | Portable equivalent | Purpose |
| --- | --- | --- |
| `make setup` | `python scripts/dev.py setup` | Install dependencies and initialize env files |
| `make dev` | `python scripts/dev.py dev` | Start DB, migrate, run apps |
| `make test` | `python scripts/dev.py test` | Backend tests and browser flows |
| `make lint` | `python scripts/dev.py lint` | Ruff, mypy, ESLint, Prettier, TypeScript |
| `make build` | `python scripts/dev.py build` | Production frontend build |
| `make migrate` | `python scripts/dev.py migrate` | Upgrade database to head |
| `make db-up` | `python scripts/dev.py db-up` | Start PostgreSQL and wait for health |
| `make db-down` | `python scripts/dev.py db-down` | Stop DB without deleting data |

On Windows use the Python commands without Make or PowerShell activation; direct npm commands can use `npm.cmd`. To run apps individually, use the backend virtual environment to run `python -m uvicorn app.main:app --reload` from `backend/`, and `npm run dev` from `frontend/`. Authentication requires a migrated PostgreSQL database; `/health` is liveness only.

## Testing

Install the browser once from `frontend/`:

```sh
npx playwright install chromium
```

On Linux CI, use `npx playwright install --with-deps chromium`. Then run `make test` or its portable equivalent. Browser tests launch isolated servers on ports 3010/8010 and a temporary migrated SQLite database, exercise the real API, and never modify your development data. They cover signup, optional connection setup, preferences, saved drafts, logout/login, route protection, and the LEARN upload to mock publish flow. Generated traces stay ignored.

Backend tests run with `backend/.venv` and use temporary databases created with Alembic. Local PostgreSQL tests are opt-in: start/migrate a disposable PostgreSQL database and set `RELAY_TEST_DATABASE=1` (PowerShell: `$env:RELAY_TEST_DATABASE="1"`; POSIX: `export RELAY_TEST_DATABASE=1`). API tests then create isolated schemas; the test account needs schema-create permission. CI runs this mode, including concurrent approval resolution, plus schema-drift and migration upgrade/downgrade/re-upgrade checks. SQLite tests do not claim to validate PostgreSQL locking.

Frontend versions are locked in `package-lock.json`; backend dependencies are pinned in `requirements-dev.lock`. Refresh in a clean environment, omit the editable Relay path from the lock file, and rerun checks. No benchmarks are claimed.

## API scope

- `/auth/register`, `/auth/login`, `/auth/logout`: library-managed Relay authentication.
- `/users/me`, `/users/me/onboarding`, `/preferences`: profile, onboarding and validated preferences.
- `/workflow-definitions`, `/workflow-runs`, `/workflow-runs/{id}/events`: definitions, owned drafts and history. Run lists support definition, status, date, incomplete-state filtering, limit and offset.
- `/workflows/learn`: LEARN run creation, private source upload/download, parse, summarize, edit proposed summary, execute approved mock publishing, and owned artifact lookup.
- `/approvals`: owned requests and exact-payload approve/reject. Requests are produced only by internal fixture/service planning for now.
- `/connections`: safe metadata/disconnect; authorize/callback return authenticated 501 responses.

No arbitrary state-change, audit-edit, real external-artifact, or generic workflow-execution endpoint exists. Unsafe requests require the configured Origin header as well as a session where applicable.

## Boundaries and next phase

Approval snapshots, lifecycle rules and audit records are implemented. The LEARN slice proves one reviewed document-to-action path with local mock execution. Provider adapters, refresh workers, remote revocation, real Notion publishing, retrieval, account recovery/email verification, production abuse protection and deployment hardening remain outstanding. See [authentication](docs/security/authentication.md), [external connections](docs/security/external-connections.md), and [AI and document handling](docs/security/ai-and-document-handling.md) for precise limits.

The recommended next phase is real Notion OAuth and destination binding for LEARN, or Agent Runtime integration behind the existing `RuntimeClient` contract. Plan and Collaborate remain later work.

## License

MIT. See [LICENSE](LICENSE).
