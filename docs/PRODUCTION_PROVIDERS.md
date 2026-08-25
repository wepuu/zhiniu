# Production Provider Operations

## Managed configuration

DeepSeek and Resend may be managed from `/admin` after one deployment-level credential key ring
is injected. Provider API keys are AES-256-GCM encrypted in PostgreSQL; encryption keys remain
outside the database and version control. Changes use draft, exact-version diagnostic and publish
stages. API and Celery workers resolve the published revision at call time.

```text
PROVIDER_CREDENTIAL_ACTIVE_KEY_ID=v1
PROVIDER_CREDENTIAL_KEY_RING=v1:<32-byte-base64-key>
MANAGED_PROVIDERS_HARD_DISABLED=false
```

Generate a key with `uv run python -m zhaoniu_api.cli generate-provider-encryption-key`. For
rotation, add the new key to the ring, make it active, run
`reencrypt-provider-credentials --to-key-id <id> --operator-email <email>`, then remove the old key.
The hard-disable switch never falls back to environment credentials.

## Resend

Set `EMAIL_DELIVERY_MODE=resend`, a restricted API key, verified sender/domain and Svix-compatible
webhook secret. API requests enqueue delivery to Celery; the request process does not contact
Resend. A logical delivery key becomes the provider idempotency key. Webhooks are signature- and
timestamp-verified before JSON parsing, deduplicated by provider event ID, and applied in event-time
order. Only delivery state and bounded reason codes are retained.

The console diagnostic sends one clearly labelled message to the current verified operator using a
domain-scoped Sending access key. Delivery acceptance is not proof of inbox placement; use the webhook lifecycle
for submitted, delivered, delayed, bounced, failed, complained and suppressed states.

Phase 19 non-production acceptance must use a verified test domain and mailbox. Run the desktop
Playwright account lane with one-time environment values `E2E_INVITE_CODE`, `E2E_ACCOUNT_EMAIL`
and `E2E_ACCOUNT_PASSWORD`; then supply the received links as `E2E_VERIFICATION_URL` and
`E2E_RESET_URL` with `E2E_REPLACEMENT_PASSWORD`. These values must never be written to the
repository or baseline report. A skipped account lane is not evidence of email readiness.

## DeepSeek through LiteLLM

Stock-health model identifiers remain deployment configuration. The Phase 17 explanation lane is
separately fail-closed and allows `deepseek/deepseek-v4-flash` only. It uses provider JSON-object
mode and then runs Pydantic, citation, scope, numeric-claim and language validators.
Requested model, provider-returned actual model and capability mode are stored with call audit.

The console diagnostic performs one minimal structured-output request and records only status,
latency and a redacted reason code. It does not persist the probe response, prompt, credentials or
reasoning. Keep per-provider concurrency and daily call limits low until real usage measurements
justify changes.

Required explanation configuration:

```text
LLM_ENABLED=true
LLM_STRUCTURED_OUTPUT_MODE=json_object
AI_EXPLANATION_ENABLED=true
AI_EXPLANATION_MODEL_CHAIN=deepseek/deepseek-v4-flash
DEEPSEEK_API_KEY=<secret manager value>
```

These legacy environment values remain a bootstrap source until a database revision is published.
After publication, the database configuration is authoritative for that provider.

The diagnostic and explanation request both disable thinking, tools, streaming and SDK retries.
Production activation remains subject to legal and financial-data approval gates.

## AKShare market-data diagnostics

AKShare remains a development and technical-evaluation source. Diagnose one stock without writing
market data with:

```text
uv run python -m zhaoniu_api.cli diagnose-market-provider 600519
```

The command performs the same bounded two-attempt provider request as the sync adapter and emits
only a stable, redacted reason code. Proxy, timeout, connection and rate-limit failures are
retryable; invalid responses and canonical data-quality failures are not. A failed diagnostic does
not advance the latest trade date or relabel retained bars as fresh.
