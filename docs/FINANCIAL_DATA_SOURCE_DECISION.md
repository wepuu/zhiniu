# Phase 2 Financial Data Source Decision

Decision date: 2026-08-16.

## Selected technical-evaluation endpoints

| Dataset              | Adapter call                  | Upstream surfaced by AKShare | Verified capability                                                                             | Known limitation                                                 |
| -------------------- | ----------------------------- | ---------------------------- | ----------------------------------------------------------------------------------------------- | ---------------------------------------------------------------- |
| Three statements     | `stock_financial_report_sina` | Sina                         | Typed report facts, report/announcement dates, CNY, audit state, consolidated type, update time | Date-only disclosure; no authoritative historical revision chain |
| Historical valuation | `stock_zh_valuation_baidu`    | Baidu                        | PE-TTM, PB, PCF, total market cap; three-year daily-scale history                               | No PS-TTM; access and redistribution rights unconfirmed          |

AKShare `1.18.91` is the only Phase 2 registered financial provider. It is suitable for local
development and technical evaluation only. Production display, caching, redistribution,
attribution, retention, SLA and commercial use remain `TBD / requires legal review`.

## Real capability gate results

- `600519`: 2019 onward, 90 source statement rows normalized into 30 report revisions; 4,388
  three-year valuation observations across PE-TTM, PB, PCF, and market cap.
- `300750`: same report and valuation coverage used to validate growth-company statements.
- `000001`: 2023 onward, 42 source rows normalized into 14 report revisions. Bank classification
  is based on material loans and customer-deposit facts; the general-company metric template is
  not applied.
- Repeating identical sync windows is skipped by deterministic idempotency keys.

Provider selection remains per dataset. Tushare is a future candidate because its official
contracts expose richer announcement/report/update semantics, but it was not registered without a
user-supplied credential, capability test, and legal decision. Real multi-provider fallback is not
claimed in Phase 2.
