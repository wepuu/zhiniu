# Production Provider Operations

## Resend

Set `EMAIL_DELIVERY_MODE=resend`, a restricted API key, verified sender/domain and Svix-compatible
webhook secret. API requests enqueue delivery to Celery; the request process does not contact
Resend. A logical delivery key becomes the provider idempotency key. Webhooks are signature- and
timestamp-verified before JSON parsing, deduplicated by provider event ID, and applied in event-time
order. Only delivery state and bounded reason codes are retained.

The console diagnostic checks API authentication and configured-domain verification without
sending an email. Delivery acceptance is not proof of inbox placement; use the webhook lifecycle
for submitted, delivered, delayed, bounced, failed, complained and suppressed states.

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

The diagnostic and explanation request both disable thinking, tools, streaming and SDK retries.
Production activation remains subject to legal and financial-data approval gates.
