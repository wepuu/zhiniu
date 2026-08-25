# Account recovery

Phase 12 implements email verification and password recovery as deterministic account-lifecycle
workflows. Tokens are generated with cryptographic randomness, stored only as SHA-256 digests,
expire after the configured TTL and are consumed once. Resending revokes outstanding verification
tokens. Completing a password reset revokes every session, including the requesting browser.

`POST /api/v1/auth/password-reset/request` deliberately returns HTTP 202 with generic copy for
known and unknown addresses. Rate limiting is Redis-backed and fail-closed in production. Logs,
database rows and API errors must not contain plaintext tokens, message bodies or SMTP credentials.

Development may set `EMAIL_DELIVERY_MODE=disabled`; delivery attempts are then audited as disabled.
A controlled Beta release requires a complete, diagnosed transactional-email configuration
(currently SMTP or Resend) and a public HTTPS base URL.
