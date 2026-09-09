# Notion publishing architecture

Real Notion publishing is intentionally hidden behind the connector interface. Workflow services create approved Relay actions; connector code owns OAuth, destination discovery, API requests, provider errors, and Notion block formatting.

```mermaid
sequenceDiagram
    actor Student
    participant UI as Relay UI
    participant API as Relay API
    participant DB as Database
    participant Runtime as RuntimeClient
    participant Local as LocalRuntimeClient
    participant Connector as NotionConnector
    participant Notion as Notion API

    Student->>UI: Approve exact study-page proposal
    UI->>API: Approve payload
    API->>DB: Freeze approved payload
    Student->>UI: Publish to Notion
    UI->>API: Execute LEARN run
    API->>DB: Check artifact idempotency key
    API->>Runtime: Submit approved payload
    Runtime->>Local: Execute create_notion_study_page
    Local->>Connector: create_study_page(action, idempotency_key)
    Connector->>Notion: POST /v1/pages
    Notion-->>Connector: Created page id/url
    Connector-->>Local: ExternalArtifactResult
    Local-->>API: ExecutionSnapshot
    API->>DB: Store external artifact
    API->>DB: Complete workflow
    API-->>UI: Completed run and artifact
```

## OAuth sequence

```mermaid
sequenceDiagram
    actor User
    participant UI as Relay UI
    participant API as Relay API
    participant Auth as Notion Authorization Server
    participant DB as Database

    User->>UI: Connect Notion
    UI->>API: GET /connections/NOTION/authorize
    API->>DB: Store hashed state and expiry
    API-->>UI: Authorization URL
    UI->>Auth: Redirect user
    Auth-->>API: Callback with code and state
    API->>DB: Verify state is valid and unused
    API->>Auth: Exchange code with client credentials
    Auth-->>API: Workspace token response
    API->>DB: Encrypt token and persist connection
    API-->>UI: Redirect to Connections
```

## Verification decision

For page creation, Notion's create response includes the created page id and URL. Relay treats that response as sufficient confirmation and records the artifact. It avoids an extra read call because the create response is the trusted write acknowledgement and additional reads can introduce new permission/rate-limit failure modes after success.
