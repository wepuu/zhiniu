# Phase 25 Controlled Beta Readiness

Phase 25 converts the working Phase 24 watchlist loop into measurable, supportable controlled-Beta
operations. It does not approve a public launch, expand to full-market backfill, or relax financial
data licensing requirements.

## Product outcome

An operator must be able to answer three questions from retained facts:

1. Did a watchlist request start promptly?
2. When did market, deterministic research, and AI reach a usable or honest terminal state?
3. Which bounded reason is preventing readiness?

For the controlled-Beta funnel, first value is the first retained market artifact and the
deterministic research artifact for a watchlist run. Their queue-to-ready timings are projected by
the SLO metrics; no per-user copy of shared stock data is created.

The existing watchlist and company pages remain the user contract. Phase 25 adds no score,
recommendation, target price, return probability, or personalized investment advice.

## Runtime SLO contract

`GET /api/v1/admin/automation/slo?window_hours=24` is read-only and requires
`automation.read`. The query window accepts 1 to 168 hours and projects the following metrics from
`automation_runs` and `automation_run_steps`:

| Metric              | Start       | Terminal fact                                              | Target     |
| ------------------- | ----------- | ---------------------------------------------------------- | ---------- |
| Task start          | run created | run started                                                | 10 seconds |
| Market ready        | run created | successful `market_sync`                                   | 60 seconds |
| Deterministic ready | run created | successful `research_build`, or unchanged current research | 10 minutes |
| AI terminal         | run created | successful, failed, skipped, or blocked `ai_research`      | 10 minutes |

P95 uses the nearest-rank method. A metric with no samples is `unknown`, never automatically
passing. A watchlist run still pending or running after 10 minutes is stale. Acceptable run terminal
states are `succeeded`, `succeeded_with_warnings`, and `partial`; research coverage continues to
distinguish ready, partial, unsupported, missing source data, and failed states.

### Trading-day freshness contract

Readiness now exposes `market_freshness` (`current`, `stale`, or `unknown`) and an optional
`expected_trade_date`. The expected date is derived only from the versioned `trading_sessions`
table, keyed by exchange and calendar version. Migration `20260914_0029` creates this source-backed
contract without seeding guessed weekdays or holidays. For development/evaluation, operators may
ingest the free AKShare/Sina date list with `uv run python -m zhaoniu_api.cli
sync-trading-calendar`; the normalizer records explicit SSE/SZSE rows and 09:30–15:00 China-time
session boundaries. This does not make the source commercially approved: until a licensed calendar
provider is accepted for Beta, production gates continue to treat the source as evaluation-only.
A missing calendar still returns `unknown`, and a future-dated bar never counts as current.
The endpoint has no publication timestamp, so ingestion time is retained conservatively as
`known_at`.

Market freshness also requires a successful `trading_calendar` sync audit within 36 hours. A
retained calendar row without a recent successful check cannot keep old market data marked current;
the readiness API returns `calendar_status=stale` or `unknown` and suppresses
`expected_trade_date`. The latest closed session becomes expected only after a 30-minute
post-close publication grace period. Exchange calendars do not prove whether an individual
security was suspended, so user copy says that coverage needs confirmation rather than claiming a
Provider failure. BSE remains unsupported by this SSE/SZSE calendar contract.

### Immutable reliability observations

Migration `20260914_0030` adds append-only `beta_reliability_observations`. An elevated operations
user may freeze a 24- or 48-hour database-backed observation through
`POST /api/v1/admin/automation/observations`. Each record binds the window to the release commit,
immutable API/Web image digests, migration head and configuration fingerprint, and stores the SLO
projection, calendar health, bounded blocking reasons and a deterministic result fingerprint.

The initial `beta-reliability-v1` rule set requires at least 20 samples for every SLO dimension,
all four P95 targets to pass, at least 95 percent acceptable terminal runs, no active run older
than 10 minutes, no failed/blocked facts without a reason code, and healthy SSE/SZSE calendar
checks. A failed observation remains useful evidence and is never overwritten. Host OOM, container
restart and sustained broker-depth evidence remains a deployment/operations gate because those
facts are not currently retained in the application database.

## Controlled-Beta entry gates

All gates remain fail-closed:

- 24–48 hours of staging observation with no OOM restart or sustained Celery backlog.
- Queue, market, deterministic, and AI SLO samples visible in the operations console; unexplained
  stale runs must be zero before invitation dispatch.
- Fixed-sample Provider acceptance for `600519`, `300750`, `300376`, and `000001` against the exact
  candidate configuration and source policy.
- A commercially approved A-share data source with documented display, redistribution, retention,
  derived-data, historical-depth, rate-limit, and termination rights.
- Published healthy DeepSeek and Resend revisions, verified email lifecycle, current encrypted
  backup, and successful isolated restore drill.
- Existing Phase 20 Provider/Beta, Phase 21 invitation, and Phase 22 release gates all pass using
  current evidence rather than screenshots or operator assertion.

The release state must match the product path: `closed_deployment` keeps the emergency automation
stop enabled, while `invite_activation` requires `AUTOMATION_HARD_DISABLED=false` and
`WATCHLIST_PREPARATION_ENABLED=true`. The daily database policy remains an independent, bounded
choice; enabling user-triggered preparation does not silently enable the scheduled refresh.

AKShare and the Sina fallback remain development/evaluation inputs. Their technical health does not
satisfy the commercial-data gate.

## Licensed data acceptance track

Before integrating a production source, retain a signed decision record covering:

- stock master, daily market, financial statement, valuation, industry, and disclosure coverage;
- source publication and knowledge timestamps, revision policy, identifier mapping, and units;
- API quotas, burst behavior, outage terms, historical backfill limits, and Hong Kong egress;
- public display, redistribution, cache/retention, derived metrics, AI-context export, and deletion
  obligations;
- sandbox credentials and fixed-sample payloads suitable for Provider → Normalizer → Canonical
  Model → Repository contract tests.

The first adapter release must run alongside the evaluation adapter in acceptance mode. It may not
silently mix sources, overwrite lineage, or change a retained snapshot's knowledge cutoff.

## Rollout order

1. Deploy the SLO projection and read-only operations panel.
2. Ingest and verify the evaluation trading calendar, then observe staging for 24 hours; classify
   each failure reason and confirm queue recovery.
3. Freeze a release-bound 24-hour observation; continue to 48 hours when it passes.
4. Complete licensed-provider legal and technical acceptance, then repeat the four fixed samples.
5. Create a small invitation cohort only after all existing gates pass.
6. Review first-value completion, readiness latency, Provider usage, support feedback, backups, and
   OOM/queue guardrails daily for 48 hours before expanding the cohort.

Factor/backtest development remains deferred until point-in-time licensed history, delisting data,
corporate actions, and survivorship-bias controls are available.
