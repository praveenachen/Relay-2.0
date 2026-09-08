# System context

Relay is the student-facing application. Solid edges indicate current behavior; dotted edges indicate planned relationships. PostgreSQL is configured but stores no domain records yet.

```mermaid
flowchart LR
    User[Student] --> Frontend[Relay Frontend]
    User -->|Health and API docs| API[Relay API]
    Frontend -.->|Planned application requests| API
    API -.->|Configured, no domain persistence yet| DB[(PostgreSQL)]
    API -.->|Planned execution contract| Runtime[Agent Runtime]
    API -.->|Planned interpretation| LLM[LLM Provider]
    API -.->|Planned connector logic| Notion[Notion]
    API -.->|Planned connector logic| Calendar[Google Calendar]
    API -.->|Planned connector logic| GitHub[GitHub]
```

The frontend links to API documentation; it does not yet fetch application data. External account configuration and provider-specific interpretation belong to Relay. Runtime is separate, and its eventual execution transport is unresolved. No external service is contacted in Phase 0.
