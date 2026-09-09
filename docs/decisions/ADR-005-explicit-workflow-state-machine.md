# ADR-005-explicit-workflow-state-machine

Status: Accepted for Phases 1 and 2

# Context

Workflow runs need reviewable lifecycle rules before any automation exists.

# Options Considered

Unrestricted status writes; state inferred from logs; a central typed state machine.

# Decision

Keep a pure transition table with typed errors, and use an application service for locked persistence, timestamps, and audit events.

# Rationale

Illegal jumps and terminal-state restarts should fail deterministically. Transition tests cover every state pair.

# Consequences

API clients cannot set workflow state. Internal planning must create valid approval requests before entering review. Execution states remain future-facing.

# When We Would Reconsider

Revisit state granularity when a real workflow exposes a lifecycle that cannot be modeled without ambiguity.
