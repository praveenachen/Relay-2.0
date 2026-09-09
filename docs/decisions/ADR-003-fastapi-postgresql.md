# ADR-003-fastapi-postgresql

Status: Accepted for Phase 0

# Context

Relay needs typed request validation and transactional storage for future proposals, approvals, connections, and history.

# Options Considered

FastAPI with PostgreSQL; a TypeScript backend; a document database.

# Decision

Use FastAPI, Pydantic, SQLAlchemy 2, Alembic, and PostgreSQL. Start with synchronous database sessions.

# Rationale

Python fits future document processing, language-model adapters, and OR-Tools. PostgreSQL provides transactions and relational constraints; migrations keep schema changes reviewable.

# Consequences

There are Python and TypeScript toolchains. Sessions have explicit transaction ownership. No domain tables are created until requirements justify them. No performance experiments were performed.

# When We Would Reconsider

Revisit synchronous access if measured concurrency and database wait times justify async complexity; revisit storage only for demonstrated query or consistency requirements.

## Phase 1/2 update

Application sessions now use async SQLAlchemy with asyncpg to fit FastAPI Users and avoid blocking the event loop. Alembic and diagnostics retain synchronous psycopg access. This is an integration requirement, not a performance benchmark result.
