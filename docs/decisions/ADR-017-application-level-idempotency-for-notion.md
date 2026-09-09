# ADR-017-application-level-idempotency-for-notion

Status: Accepted for Phase 5

# Context

Retried publishing must not create duplicate study pages when Relay already recorded a successful artifact.

# Decision

Derive a stable idempotency key from the LEARN run and approval, check `ExternalArtifact` before execution, store the key with the artifact, and place a Relay action marker in the created page content.

# Consequences

Retries after a recorded success return the existing artifact. Ambiguous provider timeouts remain ambiguous because Notion page creation does not provide native exactly-once semantics.
