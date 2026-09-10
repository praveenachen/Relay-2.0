# System context

Solid edges are implemented relationships. External service calls can run in mock/local modes for development and CI.

```mermaid
flowchart LR
    User[Student] --> Frontend[Relay Next.js Frontend]
    Frontend -->|Same-origin API proxy and server session checks| API[Relay FastAPI API]
    API --> DB[(PostgreSQL)]
    API -->|RuntimeClient Protocol| Runtime[Agent Runtime]
    API -->|Typed interpretation| LLM[Language Model]
    API -->|OAuth + connector| Notion[Notion]
    API -->|OAuth + connector| Calendar[Google Calendar]
    API -->|OAuth + connector| GitHub[GitHub]
```

Relay accounts, sessions, preferences, workflow runs, approvals, encrypted connected accounts, provider OAuth flows, local/mock execution, and Agent Runtime HTTP submission exist. Relay owns OAuth configuration and connector-specific domain logic; Runtime remains independent of student workflow planning concepts and receives only approved action snapshots.
