# Relay and Agent Runtime boundary

Relay owns what should happen; Agent Runtime owns reliable execution. They remain separate repositories and deployable systems.

| Relay | Agent Runtime |
| --- | --- |
| Users, OAuth configuration, account connections | Asynchronous execution and workers |
| Document processing and AI interpretation | Queues, retries, backoff, timeouts |
| Learn, Plan, Collaborate and scheduling | Cancellation and execution state |
| Proposals, validation, approval and history | Idempotency support and structured results |
| Connector-specific domain behavior | Tracing and operational metrics |

`backend/app/runtime/client.py` defines a typed asynchronous `RuntimeClient` Protocol with submit, get, and cancel methods. Requests carry an operation identifier, JSON payload, and idempotency key. Snapshots carry execution identity, state, optional result, and error code. These are provisional contracts, not an implemented runtime API.

`LocalRuntimeClient` and `AgentRuntimeHttpClient` are future adapters. Neither exists yet; there is no fake successful executor. Runtime must not interpret lectures, assignments, courses, study sessions, Notion tasks, or GitHub issues. An eventual opaque operation payload is not permission to teach Runtime domain rules.

```mermaid
sequenceDiagram
    actor User
    participant Relay
    participant Runtime as Agent Runtime (planned)
    User->>Relay: Review exact proposed actions
    User->>Relay: Approve proposal version (planned)
    Relay->>Relay: Revalidate identity, permissions and proposal version
    Relay-->>Runtime: Submit opaque execution with idempotency key (planned)
    Runtime-->>Relay: Execution identity and structured status (planned)
    Relay-->>User: Verified outcome and workflow history (planned)
```

Approval requests and exact payload snapshots now exist in Relay. Runtime submission and verification remain future behavior. Before integration, Relay must also bind destination accounts and versioned proposal edits before submission. Edits invalidate approval. Runtime submission is not a substitute for approval or authorization. Partial success and stale provider state must remain visible to the user; retries must not duplicate side effects.

Before integration, agree operation registration, credential access, callback/connector execution placement, error taxonomy, cancellation races, result verification, authentication, tenant isolation, and idempotency retention. Credentials should not become arbitrary payload fields. Runtime cancellation will be best effort; completed external actions cannot be assumed reversible. No retry loop, queue, or execution-state persistence is implemented in Relay.
