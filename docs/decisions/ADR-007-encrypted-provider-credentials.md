# ADR-007-encrypted-provider-credentials

Status: Accepted for Phases 1 and 2

# Context

Future OAuth access and refresh tokens are sensitive database contents.

# Options Considered

Plaintext tokens; custom crypto; authenticated encryption through cryptography.

# Decision

Use Fernet behind a CredentialStore Protocol with a separately configured keyring.

# Rationale

A reviewed library provides confidentiality and integrity while domain code stays unaware of encryption mechanics.

# Consequences

A missing key fails closed. Losing keys requires reconnection. Rotation needs a reviewed re-encryption operation; API/audit schemas exclude tokens.

# When We Would Reconsider

Move the adapter to KMS-backed envelope encryption if deployment, key isolation, or compliance requirements justify it.
