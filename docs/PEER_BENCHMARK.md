# Peer Benchmark Contract

Phase 6 answers a narrow deterministic question:

> Where is this company's metric value numerically positioned within comparable peers?

It does not score investment quality, imply buy/sell action, forecast returns, or produce target
prices.

## Comparable metric policy

Fundamental peer comparisons only read `fundamental_metric_points`. They must match:

```text
metric_code
metric_version
period_end
fiscal_period
basis
unit
status = available
known_at <= knowledge_cutoff
```

Valuation comparisons use `valuation_observations` on the same `trade_date`. Phase 6 supports the
already implemented valuation observations: `pe_ttm`, `pb`, `pcf`, and `market_cap`. `ps_ttm` is
deferred until the upstream input and metric contract exist.

## Invalid values

Negative or zero PE values are excluded from PE median, quartile and percentile calculations. The
benchmark records `excluded_invalid_value_count`.

## Sample requirements

`minimum_valid_sample_size = 8`.

If fewer than eight valid peer inputs remain after comparability and invalid-value filters, the
metric status is `insufficient_peers` and no percentile is displayed.

## Percentile and rank

Numeric percentile is a mid-rank percentile:

```text
(count_less + 0.5 * count_equal) / sample_size * 100
```

Rank is descending numeric rank:

```text
1 + count(peer_or_target_value > target_value)
```

These are numeric positions, not quality rankings. UI copy must use phrases such as "同行位置",
"数值分位", or "数值排名"; it must not say "行业排名" or "综合排名".

## Immutability and idempotency

`peer_benchmark_snapshots` are immutable. Idempotency includes:

```text
symbol
taxonomy/version
peer_universe_fingerprint
knowledge_cutoff
input_fingerprint
benchmark schema version
producer version
```

Rebuilding identical inputs returns `skipped` or reuses existing results. Revised metric points,
valuation observations, or industry memberships produce a new benchmark identity.
