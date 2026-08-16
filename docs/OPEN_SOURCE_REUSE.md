# Open-source Reuse Register

Open-source code licenses do not grant rights to redistribute an upstream financial-data feed.
AKShare is therefore a development and technical-evaluation provider in Phase 1. Commercial use,
attribution, display, caching, and redistribution remain `TBD / requires legal review`.

| Project              | Repository and evaluated commit                                                                | License | Evaluation scope                                                                   | Reuse decision                                                                                                                                                       | Copied code |
| -------------------- | ---------------------------------------------------------------------------------------------- | ------- | ---------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------- |
| daily_stock_analysis | https://github.com/ZhuLinsen/daily_stock_analysis @ `5c964bf23bade6571d09a085fc42199882b77f8f` | MIT     | A-share symbol handling, AKShare fetcher, normalization, exceptions, fallback      | Rewrite the narrow contracts and adapters behind Zhaoniu ports. Its combined cleaning/indicator pipeline and multi-provider manager do not match Zhaoniu boundaries. | None        |
| StockAgent           | https://github.com/qilihei/StockAgent @ `82fbd6619e92e79172756d7c689bb1ec5dc0f8b6`             | MIT     | data-source port, sync-SDK executor wrapping, collector/storage and Redis patterns | Retain architectural lessons only. The adapters, Mongo/Redis managers, and node orchestration are coupled to a different distributed runtime.                        | None        |

Both repositories were evaluated on 2026-08-16 from their `main` branch. The local reference
working copies are Git-ignored. Detailed findings are in `docs/references/`.

## Modification and upgrade strategy

There is no vendored or extracted third-party code and therefore no local patch set. Zhaoniu owns
its provider port, canonical models, normalizer, validator, repository, and tests. A future upstream
upgrade requires pinning a new commit, reviewing its license and relevant modules again, updating
the audit, and rerunning provider fixture and contract tests before adopting any behavior change.
