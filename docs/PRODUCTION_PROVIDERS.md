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

Model identifiers remain deployment configuration. `LLM_STRUCTURED_OUTPUT_MODE=json_schema` uses
strict response schema when the configured model supports it. `json_object` uses provider JSON mode
and still runs the existing Pydantic, citation, coverage, numeric-claim and language validators.
Requested model, provider-returned actual model and capability mode are stored with call audit.

The console diagnostic performs one minimal structured-output request and records only status,
latency and a redacted reason code. It does not persist the probe response, prompt, credentials or
reasoning. Keep per-provider concurrency and daily call limits low until real usage measurements
justify changes.
