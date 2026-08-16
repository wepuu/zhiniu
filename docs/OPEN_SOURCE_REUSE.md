# Open-source Reuse Register

Open-source code licenses do not grant rights to redistribute an upstream financial-data feed.
AKShare is therefore a development and technical-evaluation provider in Phases 1–2. Commercial
use, attribution, display, caching, and redistribution remain `TBD / requires legal review`.

| Project              | Repository and evaluated commit                                                                | License | Evaluation scope                                                                           | Reuse decision                                                                                                                                                     | Copied code |
| -------------------- | ---------------------------------------------------------------------------------------------- | ------- | ------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------- |
| daily_stock_analysis | https://github.com/ZhuLinsen/daily_stock_analysis @ `5c964bf23bade6571d09a085fc42199882b77f8f` | MIT     | A-share symbols, AKShare fetchers, fallback, fundamental adapter and source-chain status   | Rewrite narrow contracts and adapters. Its float/latest-row/partial bundle is not a revisioned canonical accounting model.                                         | None        |
| StockAgent           | https://github.com/qilihei/StockAgent @ `82fbd6619e92e79172756d7c689bb1ec5dc0f8b6`             | MIT     | Async SDK boundary, collectors, Redis, Tushare daily-basic and financial-indicator manager | Retain architectural and batching lessons only. Provider-computed indicators and the distributed runtime do not match Zhaoniu formula lineage or modular monolith. | None        |

Both repositories were evaluated on 2026-08-16 from their `main` branch. The local reference
working copies are Git-ignored. Detailed findings are in `docs/references/`.

## Modification and upgrade strategy

There is no vendored or extracted third-party code and therefore no local patch set. Zhaoniu owns
its provider ports, canonical models, normalizers, validators, repositories, deterministic formulas
and tests. A future upstream upgrade requires pinning a new commit, reviewing its license and
relevant modules again, updating the audit, and rerunning provider fixtures and contract tests
before adopting any behavior change.
