# OAuth security

Relay stores OAuth credentials only after a provider callback passes state validation. Authorization state values are random, short-lived, single-use, and stored as hashes. Callback handlers validate `state`, `code`, and provider `error` before exchanging credentials.

Provider tokens, authorization codes, and client secrets must never be returned to React or recorded in audit metadata. `ConnectedAccount` responses expose only safe metadata such as workspace name, scopes, status, and provider-owned ids.

Notion uses a provider-specific token lifecycle. Relay stores access tokens encrypted with `TOKEN_ENCRYPTION_KEY`, keeps refresh token and expiry nullable, and does not pretend every OAuth provider can be refreshed or revoked through the same behavior.

Disconnect marks Notion connections revoked and clears stored token fields. Publishing authorization failures also revoke the affected Notion connection.
