# Zhaoniu Engineering Rules

Zhaoniu is a production-oriented, multi-user A-share research SaaS. Keep it a modular monolith with background workers until measured scale requires otherwise. Product language must remain research-oriented and must not imply buy, sell, target price, return probability, or personalized investment advice.

## Non-negotiable boundaries

1. The frontend never accesses the database; it uses the versioned REST API.
2. Business services never call AKShare, Tushare, BaoStock, or another vendor SDK directly.
3. External financial data always flows through Provider -> Normalizer -> Canonical Model -> Repository.
4. Financial metrics are computed only by deterministic Python or SQL code with tests.
5. An LLM must not calculate financial indicators.
6. AI results use explicit structured schemas by default; Markdown is presentation, not the contract.
7. Every user-owned record includes and is queried with `user_id`.
8. Shared stock data is stored once globally, never duplicated per user.
9. Background jobs require an idempotency strategy, bounded retries, deduplication, locks where needed, and queryable status.
10. Equivalent research jobs are deduplicated by symbol, data version, template version, and model version.
11. Desktop and mobile critical flows must be designed and QA'd separately.
12. Do not scatter copied StockAgent or daily_stock_analysis code into product modules.
13. Before migrating third-party code, document its source, license, local modifications, and upgrade strategy in `docs/OPEN_SOURCE_REUSE.md`.
14. UI and AI copy must not contain investment-advice semantics.
15. New behavior requires basic automated tests.
16. Database schema changes require an Alembic migration.
17. Never commit secrets, credentials, tokens, customer data, or production dumps.
18. Every API response has an explicit Pydantic schema.
19. Short-term convenience does not justify crossing a domain boundary.
20. Peer comparisons must use comparable metric codes, versions, periods, basis and units.
21. Peer benchmarks must respect `knowledge_cutoff`; future data must not enter older snapshots.
22. Frontend code must not calculate peer percentiles, ranks or benchmark statistics.
23. LLMs must not select peer companies or calculate peer benchmarks.
24. Peer numerical position must not be presented as investment quality, recommendation or ranking.
25. Financial issuer templates must not be mixed in the same peer universe.
26. Industry classifications must retain source, version and lineage.
27. A disclosure document is evidence, not automatically a corporate event.
28. Structured corporate-event facts must remain staged until matched to a retained disclosure.
29. Event attention belongs to a versioned radar snapshot, not the immutable event record.
30. Event processing must preserve publication, knowledge, effective and ingestion time semantics.

## Standard commands

From the repository root:

```text
pnpm install
pnpm lint
pnpm format:check
pnpm typecheck
pnpm test
pnpm build
uv sync --all-groups
uv run ruff check .
uv run mypy apps/api/src apps/worker/src
uv run pytest
docker compose config
```

Commands must remain usable from Windows PowerShell, Linux, and Docker. Prefer cross-platform package scripts over shell-specific tricks.

## Architecture habits

- API routes validate and translate. Application services coordinate. Domain code owns rules. Repositories own persistence. Providers own vendor access.
- Keep raw, clean, derived metric, research context, and AI research data distinct.
- Use `/api/v1/*` for public API routes and generate the TypeScript client from OpenAPI when contracts become stable.
- Long-running data, research, report, notification, and backtest work belongs in Celery, not a FastAPI request.
- Public research snapshots are shared; only analysis that actually contains a user's private data is user-specific.
