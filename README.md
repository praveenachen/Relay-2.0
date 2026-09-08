# Relay

Academic information becomes useful when it leads to a clear next step. Relay is a student workflow platform designed to turn unstructured inputs into structured proposals and human-approved actions.

**Status: Phase 0 foundation.** The frontend shell and FastAPI health endpoint run. Database tooling, runtime contracts, and CI are configured. Workflows, authentication, approvals, and external integrations are not implemented.

## Three planned workflows

| Workflow | Intended outcome |
| --- | --- |
| Learn | Lecture notes become structured summaries in Notion. |
| Plan | Notion tasks, Google Calendar availability, and student preferences become a realistic study schedule. |
| Collaborate | Meeting transcripts become action items in Notion and technical work in GitHub. |

These are the only three planned core workflows. The current frontend presents their direction, with no executable workflow controls.

## Technical thesis

How do we safely convert probabilistic interpretation of unstructured information into deterministic actions across external systems?

```text
Input -> Understand -> Structure -> Validate -> Propose
  -> Human review -> Approve -> Execute -> Verify
```

Relay decides **what should happen**. A separate Agent Runtime repository will own **how it executes reliably**. Relay owns domain interpretation, planning, approvals, users, OAuth, and connector-specific behavior. Runtime owns queues, retries, timeouts, cancellation, idempotency support, execution state, tracing, and operational metrics. The runtime interface is currently a Python Protocol only.

## Architecture and repository

```text
frontend/              Next.js App Router, React, TypeScript, Tailwind
  app/                 Application shell and design tokens
  components/          TanStack Query provider
  lib/                 Zod-validated public configuration
backend/
  app/api/             HTTP routing (health only)
  app/core/            Typed settings
  app/db/              SQLAlchemy base and lazy sessions
  app/runtime/         Domain-neutral execution contract
  app/schemas/         API response schemas
  alembic/             PostgreSQL migration baseline
  tests/               Smoke, contract, and opt-in database tests
scripts/dev.py         Cross-platform developer commands
.github/workflows/     Frontend and backend CI
docs/                 Architecture, ADRs, and security notes
```

Application services, domain objects, repositories, connectors, AI, auth, and workflow packages will be added when they have real responsibilities. Future dependency direction is API -> application services -> domain and repository/connector/runtime interfaces; infrastructure implements those interfaces. Domain rules never belong in route handlers. No empty business layers are simulated.

See [system context](docs/architecture/system-context.md), [containers](docs/architecture/container-diagram.md), and [runtime boundary](docs/architecture/relay-agent-runtime-boundary.md). Decisions are recorded in [ADRs](docs/decisions).

## Local setup

Prerequisites: Python 3.12, Node.js 24 LTS with npm, Docker with Compose v2. GNU Make is optional. Run commands from the repository root.

```sh
python scripts/dev.py setup
python scripts/dev.py dev
```

Setup creates `backend/.venv`, installs locked dependencies, and copies example environment files only when local files do not already exist. Dev starts PostgreSQL, applies migrations, and runs both servers in the foreground. Ctrl+C stops the servers; PostgreSQL remains available until `db-down`. Do not run multiple copies of `dev` on the same ports.

- Frontend: http://localhost:3000
- API liveness: http://localhost:8000/health
- OpenAPI UI: http://localhost:8000/docs

On Windows, use `python scripts/dev.py ...` without Make or PowerShell activation. For direct npm commands in restricted PowerShell environments, use `npm.cmd`.

| Make command | Portable equivalent | Purpose |
| --- | --- | --- |
| `make setup` | `python scripts/dev.py setup` | Install dependencies and local env files |
| `make dev` | `python scripts/dev.py dev` | Start database and both apps |
| `make test` | `python scripts/dev.py test` | Backend smoke and contract tests |
| `make lint` | `python scripts/dev.py lint` | Ruff, mypy, ESLint, TypeScript |
| `make build` | `python scripts/dev.py build` | Frontend production build |
| `make migrate` | `python scripts/dev.py migrate` | Upgrade database to head |
| `make db-up` | `python scripts/dev.py db-up` | Start PostgreSQL and wait for health |
| `make db-down` | `python scripts/dev.py db-down` | Stop PostgreSQL; preserve data volume |

To run apps separately, run `.venv/bin/python -m uvicorn app.main:app --reload` from `backend/` (Windows: `.venv/Scripts/python.exe`), and `npm run dev` from `frontend/`. Neither application needs a live database to serve its Phase 0 shell/health endpoint.

Root `.env` configures the backend and Compose. `frontend/.env.local` configures the public API documentation link. If changing database credentials/port, update `DATABASE_URL` consistently; changing Compose credentials does not reinitialize an existing data volume. Blank future integration settings are deliberately unused. Never put secrets in `NEXT_PUBLIC_*` variables.

## Database and validation

PostgreSQL 17 runs bound to localhost with a named data volume. SQLAlchemy constructs its engine lazily. Session callers will own commit/rollback decisions. The initial Alembic revision establishes version history without domain tables. No automatic schema creation runs at API startup.

From `backend/`, use the virtual environment Python:

```sh
python -m alembic upgrade head
python -m alembic check
python -m alembic revision --autogenerate -m "describe schema change"
```

Review generated migrations before applying them; register future models in `alembic/env.py`. Downgrades may destroy data once real schema migrations exist.

Database tests skip locally unless `RELAY_TEST_DATABASE=1` is set and migrations have been applied. In PowerShell: `$env:RELAY_TEST_DATABASE="1"`; in POSIX shells: `export RELAY_TEST_DATABASE=1`. Use a disposable development/test database. CI runs these tests against PostgreSQL and exercises upgrade/downgrade/upgrade plus schema drift detection. `/health` checks process liveness only, not database readiness.

Frontend dependency versions are locked in `package-lock.json`; backend development dependencies are pinned in `requirements-dev.lock`. Refresh intentionally in a clean environment and rerun checks. CI checks lint, formatting, types, backend tests, migrations, Compose configuration, and a frontend production build. No benchmark or production-readiness claim is made.

## Roadmap

1. **Phase 0:** repository and application foundation (this repository).
2. **Recommended Phase 1:** define the first Learn domain contracts, document/proposal lifecycle, validation rules, and approval semantics using fixtures before external writes.
3. Later: authentication, secure account connections, typed language-model adapter, document processing, and a reviewed Learn vertical slice.
4. Later: Plan with OR-Tools/CP-SAT, Collaborate, and the separate Agent Runtime adapter when its contract is agreed.

No later phase has started. No OpenAI, Notion, Google Calendar, GitHub, or Agent Runtime calls exist.

## License

MIT. See [LICENSE](LICENSE).

## Stack references

[Next.js installation](https://nextjs.org/docs/app/getting-started/installation), [FastAPI settings](https://fastapi.tiangolo.com/advanced/settings/), and [Alembic migrations](https://alembic.sqlalchemy.org/en/latest/tutorial.html) describe the framework conventions used here.
