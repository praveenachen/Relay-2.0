# Provider credential storage

The domain owns a `CredentialStore` Protocol with encrypt/decrypt methods. The infrastructure implementation uses [cryptography Fernet / MultiFernet](https://cryptography.io/en/stable/fernet/) for authenticated encryption. No custom cipher, nonce scheme, or hashing construction is implemented.

Connection services receive the store as a dependency. Only encrypted strings go into `access_token_encrypted` and `refresh_token_encrypted`. Safe connection response schemas include metadata, expiry, scopes and status only. Audit records store connection identity/provider, never credentials. Tokens are not accepted in public connection endpoints in this phase.

`TOKEN_ENCRYPTION_KEY` is a secret setting. Blank is permitted while OAuth is unavailable; any attempt to instantiate credential storage without a valid key fails closed with a safe configuration error. There is no development fallback key. Encryption does not reuse a Relay session secret.

To generate a key locally from the backend virtual environment:

```sh
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Put it in the ignored root `.env` or a production secret manager, never in Git or `NEXT_PUBLIC_*`. Do not log it. Losing the key makes existing provider credentials unreadable and requires reconnection.

For staged key rotation, the setting accepts comma-separated keys, newest first. New encryption uses the first key; decryption tries the keyring. Re-encrypt existing rows through a reviewed maintenance operation before retiring old keys; an automated rotation job is not implemented yet. Test coverage verifies round-trip encryption, old-key reads, wrong-key failure, and tamper detection.

Disconnect clears both encrypted tokens locally and sets REVOKED. Remote provider revocation is not claimed: real provider adapters must implement and verify that later. Database backups and encryption keys need separate access controls. Encryption at rest does not protect a compromised application process that can read both.
