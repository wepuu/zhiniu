# Peer Research

Phase 6 adds global shared peer research. It is not user-owned and does not include private
watchlist data, so the public read APIs do not require `user_id`.

## Build path

```text
IndustryMembership
  -> PeerUniverseResolver
  -> FundamentalMetricPoint / ValuationObservation selector
  -> PeerBenchmarkEngine
  -> CompanyPeerMetricPosition
  -> REST API
  -> Desktop / Mobile peer cards
```

CLI and future Celery tasks must call the same application service:

```text
uv run python -m zhaoniu_api.cli sync-industries
uv run python -m zhaoniu_api.cli build-peer-benchmark 600519
uv run python -m zhaoniu_api.cli build-peer-research 600519
```

## APIs

```text
GET /api/v1/stocks/{symbol}/peers
GET /api/v1/stocks/{symbol}/peer-comparisons
```

`peer-comparisons` supports an optional dimension filter:

```text
growth | profitability | quality | balance | valuation
```

Statuses are explicit: `available`, `unsupported_template`, `missing_industry`,
`missing_metric`, `incomparable_basis`, `insufficient_peers`, `invalid_inputs` and `not_built`.

## Frontend

The stock page keeps four top-level tabs:

```text
研究 / 行情 / 财务 / 估值
```

Peer research appears inside the 研究 tab as a second-level "同行位置" view. Desktop and mobile
render separately using metric cards and a distribution bar, not radar charts or scores.

## AI boundary

Phase 6 does not depend on AI. If a later AI context consumes peer benchmark evidence, the LLM must
not calculate peer values, copy financial numbers, select peer companies, or present the result as
investment advice.
