# Containers and dependency direction

```mermaid
flowchart TB
    Browser[Browser] --> Web[Next.js frontend]
    Browser -->|Health or docs| API[FastAPI API]
    Web -.->|Planned JSON requests| API
    API -.-> Services[Planned application services]
    Services -.-> Domain[Planned domain rules]
    Services -.-> Repositories[Planned repository interfaces]
    Services -.-> Connectors[Planned Relay connectors]
    Services -.-> Contract[RuntimeClient Protocol only]
    Repositories -.-> SQL[Configured SQLAlchemy and Alembic]
    SQL -.-> DB[(PostgreSQL)]
    Contract -.-> Runtime[Planned Agent Runtime adapter]
    Connectors -.-> Providers[Notion / Google Calendar / GitHub / LLM]
```

Local processes: browser-facing Next.js on 3000, FastAPI on 8000, and Compose PostgreSQL on localhost 5432. Only PostgreSQL is containerized. There is no worker or runtime service in this repository.

Routes will translate HTTP requests and responses, delegate to services, and avoid business rules. Services will coordinate domain validation, repositories, and connector/runtime ports. Domain code must not import FastAPI, provider SDKs, or transport clients. SQLAlchemy and concrete transport adapters are infrastructure; API schema models are distinct from future persistence models.

Synchronous SQLAlchemy is sufficient for this foundation. Future blocking DB work must run in synchronous handlers/dependencies or an appropriate thread context, not block the async event loop. No runtime submit endpoint exists.
