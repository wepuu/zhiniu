# Versioned feature access

Feature access is resolved by the backend for every authenticated request. Routes do not infer
access from frontend state, code shape or a mutable display label.

## Resolution model

The effective feature set is the union of:

1. the user's immutable base plan version; and
2. every active, non-revoked access grant whose validity window contains the current time.

`legacy_beta`, `basic` and `advanced` are internal catalog keys. Plan versions preserve the exact
feature flags and limits used when an account or grant was created. Changing a future catalog entry
therefore does not rewrite historical access.

The public contract is `GET /api/v1/me/access`. It returns user-facing access status, enabled
features, effective limits, validity and support URL. `GET /api/v1/me/entitlements` remains the
machine-oriented compatibility endpoint. The UI may use these responses for presentation, but the
API repeats authorization checks on protected operations.

Natural-language research parsing and the larger saved-research limits require advanced access.
The Phase 17 research assistant uses the versioned `ai_research_explanation` feature and
`ai_explanations_daily` limit. Basic is disabled with zero daily requests; advanced allows ten UTC
day requests. Existing legacy Beta accounts retain their historical evaluation access. Each new or
explicitly retried user request consumes quota atomically; cache attachment still counts as a user
request so concurrency cannot bypass the limit.
Core deterministic research, watchlists and existing legacy-beta behavior remain available under
their resolved limits. A denied request uses the stable `advanced_access_required` error code and
does not reveal operator or grant metadata.
