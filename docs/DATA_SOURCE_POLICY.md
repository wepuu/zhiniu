# Phase 1 data-source policy

AKShare is registered only as a development and technical-evaluation source. Its package license
does not establish permission to commercially display, cache, or redistribute the upstream market
data returned by individual endpoints.

Before any production or commercial use, legal/product owners must confirm the upstream source,
terms, attribution, display and redistribution rights, retention limits, service stability, and a
licensed replacement/fallback strategy. Until that review is recorded, all such fields are
`TBD / requires legal review`.

Phase 1 stores a global copy of unadjusted A-share stock master and daily bars for technical
validation. Sync-run records retain provider identity, request window, counts, timing, status, and
a redacted exception class. Mock data may be used in isolated automated tests and demo-labelled
screens, but never as evidence of a successful external-data acceptance run.
