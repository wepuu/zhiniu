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
contract without seeding guessed weekdays or holidays. Until an approved calendar provider is
accepted and ingested, the API returns `unknown`; a missing calendar never turns into a false
provider failure and a future-dated bar never counts as current.

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
2. Observe staging for 24 hours; classify each failure reason and confirm queue recovery.
3. Complete licensed-provider legal and technical acceptance, then repeat the four fixed samples.
4. Create a small invitation cohort only after all existing gates pass.
5. Review first-value completion, readiness latency, Provider usage, support feedback, backups, and
   OOM/queue guardrails daily for 48 hours before expanding the cohort.

Factor/backtest development remains deferred until point-in-time licensed history, delisting data,
corporate actions, and survivorship-bias controls are available.
