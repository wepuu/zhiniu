# Phase 2 data-source policy

AKShare is registered only as a development and technical-evaluation source. Its package license
does not establish permission to commercially display, cache, or redistribute the upstream market
data returned by individual endpoints.

Before any production or commercial use, legal/product owners must confirm the upstream source,
terms, attribution, display and redistribution rights, retention limits, service stability, and a
licensed replacement/fallback strategy. Until that review is recorded, all such fields are
`TBD / requires legal review`.

Phase 2 additionally evaluates AKShare's Sina financial-report endpoint and Baidu valuation
endpoint. These upstreams were selected only because their real schemas satisfy the technical
vertical slice: three statements include report date, announcement date, currency, audit state,
statement type and source update time; valuation exposes PE-TTM, PB, PCF and market cap history.
PS-TTM is not exposed and is returned as unavailable rather than fabricated.

Announcement precision is date-only, and the endpoint does not provide a complete historical
revision ledger. Zhaoniu therefore stores every payload/normalizer version it observes and applies
a conservative availability boundary, but does not claim backtest-grade point-in-time coverage.

Sync-run records retain provider identity, request window, counts, timing, status, and a redacted
exception class. Mock data may be used in isolated tests, but never as evidence of a successful
external-data acceptance run.
