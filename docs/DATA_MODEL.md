# Phase 0 Data Model

## Entity relationships

```text
User 1--* Session (planned)
User 1--* Watchlist 1--* WatchlistItem *--1 Stock
User 1--* Subscription *--1 Plan -> Entitlements (JSON contract)
Stock 1--* MarketData / Financial / Event / Evidence (planned shared data)
Stock 1--* ResearchSnapshot (shared unique version tuple)
ResearchSnapshot *--* Evidence (planned links)
User 1--* Alert / Preference / AIChat / Usage (planned user-owned data)
```

## Implemented tables

- `users`: UUID identity, normalized unique email, Argon2id-compatible password hash, status, timestamps.
- `stocks`: globally shared canonical symbol, name, exchange, and industry reference.
- `watchlists`: user-owned named collection with indexed `user_id`.
- `watchlist_items`: explicit `user_id`, watchlist ownership, global stock reference, unique stock per list.
- `research_snapshots`: globally shared structured JSON result, unique on symbol/data/template/model versions.
- `llm_calls`: provider-neutral usage/latency/status audit foundation; no prompt body or secret storage.
- `plans`: plan identity and named entitlement keys such as `feature.ai_chat` or `limit.watchlist`.
- `subscriptions`: user-to-plan state without embedding `if plan == pro` in business logic.

Phase 0 repositories are intentionally in-memory. The SQLAlchemy models and initial Alembic migration establish persistence shape without pretending PostgreSQL-backed application behavior has been implemented.

## Isolation invariants

All user-owned repository methods require a trusted `user_id`. Identity comes from authentication, never request JSON. Shared stock and research rows do not carry `user_id`. Future PostgreSQL row-level security can reinforce application checks but cannot replace them.
