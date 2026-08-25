# Phase 20 Provider and Beta data acceptance

## Scope and decision

Phase 20 implements reproducible retained-data acceptance for the fixed A-share sample
`600519.SH`, `300750.SZ`, `300376.SZ`, and `000001.SZ`. It does not broaden market coverage,
silently repair gaps, approve a vendor license, or include the deferred email loop.

The current internal baseline is **implemented but not signed for invited Beta**. The retained run
is queryable through the operator console, administrator API, and CLI. A failed result is valid
acceptance evidence; it must not be rewritten as passed.

## Acceptance contract

Mandatory checks cover canonical stock identity, at least 220 recent daily bars, retained financial
revision history, and at least four recent valuation metrics for every fixed symbol. Industry
lineage and event evidence are conditional because issuer templates and supported event families
differ. The active DeepSeek route plus retained structured success is optional and is reported
separately.

Technical acceptance passes only when every mandatory item passes. Beta eligibility additionally
requires an approved `coverage_usage_scope`. `development_evaluation` is intentionally not an
approved Beta scope, even when global legal and data-use review flags are approved.

## First retained result (2026-08-25)

- Migration head: `20260825_0024`.
- Technical status: `failed`; Beta eligible: `false`.
- Items: 21 passed, 3 failed, 1 blocked, 1 unsupported.
- Mandatory blocker: `600519.SH` has 177 retained daily bars versus the 220-row minimum.
- Policy blocker: AKShare remains `development_evaluation` only.
- Conditional gap: `300376.SZ` has no versioned industry membership.
- Optional gap: active DeepSeek diagnostic is healthy, but the acceptance query found no retained
  successful call attributed directly to provider code `deepseek`.
- `000001.SZ` bank-template industry status remains honestly `unsupported`; it is not fabricated or
  mixed into the general-issuer peer universe.

## Operator workflow

```text
python -m zhaoniu_api.cli run-provider-acceptance
python -m zhaoniu_api.cli provider-acceptance-status
python -m zhaoniu_api.cli check-beta-readiness
```

The web console exposes the same baseline under the Provider section. Starting a new run requires
`coverage.run`, CSRF validation, and an elevated operator session. Mobile remains read-only for the
run action.

## Exit gates still open

Before invited Beta, sync the missing `600519.SH` history from an approved source, add retained
industry lineage for `300376.SZ`, configure an explicitly approved Beta provider policy, rerun the
baseline, and complete the independently deferred transactional-email gate. Provider credentials,
raw responses, prompts, message bodies, and secrets must never enter acceptance evidence.
