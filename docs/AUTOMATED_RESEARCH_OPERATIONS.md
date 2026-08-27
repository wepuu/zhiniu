# Automated Research Operations

Phase 15 turns the retained Phase 1–14 data and research services into one bounded production
pipeline. It is deliberately not a general workflow engine.

## Safety model

- Celery Beat has one fixed `automation.tick` entry and must run as a single production replica.
- PostgreSQL owns policy, run, step, attempt, lease and terminal-state truth.
- `scheduled_for` is orchestration metadata. It is never passed as `known_at` or
  `knowledge_cutoff` to research services.
- The priority universe is frozen when a run is created. A universe above the configured cap is
  blocked in full and is never silently truncated.
- The environment kill switch takes precedence over the database policy.
- Policy configuration is a versioned allow-list. Operators cannot provide cron expressions,
  task names, commands, SQL, URLs or provider credentials.
- Historical signal rules stay unchanged: a watchlist membership created after a signal's real
  `known_at` cannot receive an alert for that signal.
- Signal projection additionally records `live_incremental`, `historical_backfill`, or `replay`.
  Historical/replay projections are never alert eligible, even for a user whose watchlist predates
  the source artifact.

## Default policy

`priority_daily_refresh` is the only mandatory Phase 15 policy. Its first immutable revision uses:

- timezone: `Asia/Shanghai`
- daily check: `19:30`
- maximum universe: the smaller of 100 and the environment cap
- financial provider check: 72 hours in reporting windows, otherwise 168 hours
- corporate-event and peer lanes enabled
- automated AI disabled

Coverage is a run finalizer, not a separately scheduled policy. Screening snapshot scheduling and
industry taxonomy scheduling remain manual.

The service does not claim holiday-aware exchange scheduling. It performs at most one local-day
check; a provider response with no new trading data is a valid skip. Only the current due slot can
be caught up, within `AUTOMATION_CATCHUP_WINDOW_MINUTES`.

## Pipeline scopes

Symbol steps are ordered across the whole run before the next stage starts:

1. market sync
2. financial sync when due
3. valuation sync when market inputs changed or valuation data is absent
4. deterministic fundamental build
5. deterministic research snapshot build
6. disclosure, corporate-event and radar build
7. peer research once for each retained industry scope
8. signal projection and dispatch of newly inserted alert deliveries
9. optional AI research when the Phase 3 snapshot changed, the latest snapshot has no current
   output for the published route/prompt/schema, or the retained output is stale
10. one run-level coverage finalizer

Provider, normalizer, canonical model and repository boundaries remain inside the existing
application services. Automation never calls a vendor SDK directly.

## Status and recovery

Run states are `pending`, `running`, `succeeded`, `succeeded_with_warnings`, `partial`, `failed`,
`blocked` and `skipped`. Optional AI failure produces a warning rather than failing deterministic
research.

A step that called its application service successfully remains `succeeded` even when its retained
artifact fingerprint did not change; the step records `changed=false`. `skipped` is reserved for
work that was not invoked, such as a financial check that is not due or a downstream dependency
whose input did not change. An idempotently reused current AI output is therefore
`succeeded/changed=false`, with the bounded reason code `ai_research_output_current`.

Runs and steps use expiring leases. A new worker may reclaim an expired lease atomically. Resume
operates on the same run and policy revision, resets failed work plus skipped downstream work, and
does not repeat successful steps. Every attempt remains queryable.

## Operations workflow

The `/admin` console includes a desktop automation workspace with policy state, run history, step
detail, counts and resume controls. Mobile is intentionally read-only. Mutations require the
`automation.manage`, `automation.run` or `automation.resume` capability, a password-confirmed
elevated session, CSRF validation and an immutable operator audit event.

CLI and workers share the same application service:

```text
uv run python -m zhaoniu_api.cli automation-tick
uv run python -m zhaoniu_api.cli automation-run priority_daily_refresh
uv run python -m zhaoniu_api.cli automation-resume <run-id>
uv run python -m zhaoniu_api.cli automation-refresh-stock 600519
```

## Enablement checklist

1. Apply Alembic migration `20260821_0019`.
2. Keep `AUTOMATION_HARD_DISABLED=true` while running fixture and manual-run acceptance.
3. Verify universe size, provider limits, lease recovery, signal timestamps and alert membership
   cutoffs.
4. If AI is needed, enable it independently and keep both the per-run automation allowance and the
   Phase 14 provider limits in force.
5. Set the environment kill switch to false, restart the single Beat replica, then enable the
   database policy from an elevated operations session.
6. Monitor the first runs before leaving the policy unattended.

Emergency stop order: set `AUTOMATION_HARD_DISABLED=true`, restart Beat, then disable the database
policy. Do not delete runs or steps; they are the operational audit trail.

## Watchlist preparation

`WATCHLIST_PREPARATION_ENABLED=false` is the fail-closed default. Once accepted, adding a watchlist
membership creates a deduplicated `watchlist` run immediately. Explicit retries require ownership
and CSRF, are limited to one per symbol per user per 30 minutes and ten per day, and reuse an active
global run. Dispatch failure never rolls back membership because the fixed Beat tick recovers
pending runs. Scheduled runs check stock master at most once per 24 hours before incremental symbol
work. `AUTOMATION_HARD_DISABLED` remains the emergency stop; AI additionally requires the database
policy route, `AUTOMATION_AI_ENABLED`, a healthy managed Provider route and the per-run call cap.
