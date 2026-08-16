# Phase 1 Data Model

## Entity relationships

```text
User 1--* Session (planned)
User 1--* Watchlist 1--* WatchlistItem *--1 Stock
User 1--* Subscription *--1 Plan -> Entitlements (JSON contract)
Stock 1--* StockDailyBar
Stock 1--* DataSyncRun
Stock 1--* Financial / Event / Evidence (planned shared data)
Stock 1--* ResearchSnapshot (shared unique version tuple)
ResearchSnapshot *--* Evidence (planned links)
User 1--* Alert / Preference / AIChat / Usage (planned user-owned data)
```

## Implemented tables

- `users`: UUID identity, normalized unique email, Argon2id-compatible password hash, status, timestamps.
- `stocks`: globally shared canonical `ticker.exchange` identity plus ticker, exchange, board,
  asset/listing status, source, and collection time. `(ticker, exchange)` is unique.
- `stock_daily_bars`: globally shared clean unadjusted OHLC, `pre_close`, integer volume in shares,
  Decimal amount in CNY, provenance, and collection time; unique on
  `(symbol, trade_date, adjust_type)`. The AKShare normalizer converts its documented lots to shares.
- `data_sync_runs`: queryable provider request window, deterministic idempotency key, status,
  counts, duration, and redacted failure summary.
- `watchlists`: user-owned named collection with indexed `user_id`.
- `watchlist_items`: explicit `user_id`, watchlist ownership, global stock reference, unique stock per list.
- `research_snapshots`: globally shared structured JSON result, unique on symbol/data/template/model versions.
- `llm_calls`: provider-neutral usage/latency/status audit foundation; no prompt body or secret storage.
- `plans`: plan identity and named entitlement keys such as `feature.ai_chat` or `limit.watchlist`.
- `subscriptions`: user-to-plan state without embedding `if plan == pro` in business logic.

Stock and daily-bar APIs use PostgreSQL repositories. Watchlist remains intentionally in-memory
until Phase 2. `pct_change` is not stored: deterministic domain code computes it from clean
`close/pre_close`. `turnover_rate` and adjusted bars are deferred.

## Isolation invariants

All user-owned repository methods require a trusted `user_id`. Identity comes from authentication, never request JSON. Shared stock and research rows do not carry `user_id`. Future PostgreSQL row-level security can reinforce application checks but cannot replace them.
