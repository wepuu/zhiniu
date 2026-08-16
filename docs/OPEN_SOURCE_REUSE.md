# Open-source Reuse Register

Neither `references/StockAgent` nor `references/daily_stock_analysis` existed during Phase 0 initialization on 2026-08-16. No source, license, dependency manifest, or core module from either project was inspected, copied, or claimed as reused.

## Planned evaluation

| Project              | Candidate areas                                                                                                 | Avoid by default                                                                 | Preferred approach                                                                             | Upgrade strategy                                                                                               |
| -------------------- | --------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| StockAgent           | data-source concepts, collectors, factors, backtest boundaries, event clustering, Redis patterns, A-share rules | UI, application shell, implicit globals, tightly coupled runtime orchestration   | Adapter for providers; isolated extraction only for small licensed deterministic algorithms    | Pin evaluated upstream commit, record license/notice and local patch set, rerun contract tests before upgrades |
| daily_stock_analysis | provider fallback, symbol resolution, LiteLLM gateway ideas, analysis context, SSE progress, historical reports | product-specific workflow/UI and any code without verified license compatibility | Port interfaces first; adapter around stable behavior; extraction only after provenance review | Track upstream release/commit, keep compatibility fixtures, review migrations on each upgrade                  |

## Required process

When references are added, inspect README, LICENSE, dependency files, source layout, and the relevant core modules. Update this register with exact repository URL, commit, license, copied file/function list, modifications, notices, and tests before migration. Third-party code remains physically and logically separated from first-party modules.
