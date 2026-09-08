# Security boundaries

Phase 0 has no login, uploads, OAuth tokens, or external writes. The public health route returns only static liveness information. The local API and database are intended for development, not a public deployment.

Before handling real student data, implement identity and tenant authorization, validate uploads and retention rules, encrypt provider tokens with managed key rotation, and redact sensitive logs. Future model output is untrusted data: schema validation and deterministic domain checks precede proposals. Uploaded instructions must never grant permissions.

Explicit approval must bind to the exact action set, destination accounts, and proposal version. Recheck ownership and permissions at execution. Proposal edits require renewed approval. Keep approval history separate from Runtime execution state, and model partial outcomes without automatically reissuing successful actions.

`.env.example` contains only public local database defaults and blank future secrets. Local env files and generated artifacts are ignored. Never expose provider secrets in browser configuration. CI uses a disposable PostgreSQL service with public test credentials. Production secret storage, encryption, deployment hardening, and abuse controls remain future work.
