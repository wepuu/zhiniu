# Operations Console Runbook

Phase 14 exposes the internal console at `/admin`. It uses the normal cookie session and CSRF
boundary; operator membership is an additional server-side authorization layer.

## Roles

- `viewer`: dashboard, coverage, automation, provider and audit reads only.
- `support`: exact user lookup, session revocation, email-verification resend, invitations,
  user-bound access codes and feedback triage.
- `operations`: coverage/AI/automation task dispatch, automation policy management, feedback
  triage and provider diagnostics.
- `security_admin`: the combined capability set plus account status changes.

Grant or revoke membership through the explicit CLI. Membership changes and all sensitive console
actions are audited.

```text
uv run python -m zhaoniu_api.cli grant-operator user@example.com security_admin
uv run python -m zhaoniu_api.cli list-operators
uv run python -m zhaoniu_api.cli revoke-operator user@example.com
```

Session revocation, account status, email resend, invitation/access-code creation, provider
diagnostics and background research execution require a recent password confirmation. The
elevation expires after 15 minutes by default. Mobile is intentionally read-only for high-risk
actions.

The Phase 15 automation view shows only allow-listed policy fields and database-owned run state.
Policy changes, immediate runs, single-stock refresh and failed-run resume require elevation and
produce operator audit events. Mobile keeps this view read-only. See
`docs/AUTOMATED_RESEARCH_OPERATIONS.md` for enablement and emergency-stop order.

The AI dashboard also reports explanation requests, shared outputs, cache attachments, output
tokens and failures for the previous day. It never exposes prompts, provider responses, reasoning
or user-private request content. DeepSeek diagnostics use the Phase 17 JSON-object profile with
thinking disabled.

The provider workspace exposes encrypted DeepSeek and Resend configuration to `security_admin`
members only. Saving, importing environment values, diagnosing drafts, publishing, disabling and
credential removal require elevation. `operations` may read managed configuration metadata and
diagnose the active provider. Secret fields are write-only and never appear in API responses or the
audit stream. Mobile keeps the configuration workspace read-only.

The audit stream stores action keys, actor role, bounded target identity, outcome and safe metadata.
It must never contain passwords, plaintext activation/invitation codes, session tokens, API keys,
full email bodies, provider responses, model prompts or natural-language screening input.

Before a production launch, run:

```text
uv run python -m zhaoniu_api.cli check-production-readiness
```

This command only reports `configuration_valid` when `APP_ENV=production` and all production
security constraints pass.
