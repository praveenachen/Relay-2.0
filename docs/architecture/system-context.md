# System context

Solid edges are implemented relationships; dotted edges are planned integrations.

```mermaid
flowchart LR
    User[Student] --> Frontend[Relay Next.js Frontend]
    Frontend -->|Same-origin API proxy and server session checks| API[Relay FastAPI API]
    API --> DB[(PostgreSQL)]
    API -.->|RuntimeClient Protocol only| Runtime[Agent Runtime]
    API -.->|Planned interpretation| LLM[LLM Provider]
    API -.->|Planned OAuth and connector| Notion[Notion]
    API -.->|Planned OAuth and connector| Calendar[Google Calendar]
    API -.->|Planned OAuth and connector| GitHub[GitHub]
```

Relay accounts, sessions, preferences, draft runs, lifecycle services and approval persistence exist. Connected-account persistence and encryption exist but provider OAuth routes return 501. No external integration is contacted. Relay owns OAuth configuration and connector-specific domain logic; Runtime must remain independent of student and provider-domain concepts.
