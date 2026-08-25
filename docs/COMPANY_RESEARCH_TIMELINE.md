# Company Research Timeline

The company timeline is a read-only company-level view over retained `research_signals`. It is not
a fourth research-fact domain and has no build table or worker. Fundamental observations, peer
position observations and immutable corporate-event versions remain authoritative.

`GET /api/v1/stocks/{symbol}/timeline` freezes a `query_cutoff` on the first page. At that cutoff it
keeps only the latest signal for each `symbol + source_kind + dedup_group_key` before attention
filtering, summary counts and cursor pagination, then orders rows by `known_at DESC, id DESC`. The
opaque cursor binds the cutoff, position and filter hash. Upcoming events are hydrated separately
from the latest eligible event-radar snapshot and ordered by their effective date; they never
replace disclosure-time ordering.

Timeline items retain exactly one source artifact and route evidence back to the existing Phase 3,
6 or 7 API. AI output is not a timeline fact. Corporate-event cards show the latest signal per
event thread, while the event-thread endpoint continues to return every retained event version in
known-time order.

Historical and replay projections may populate the timeline but set `alert_eligible=false`.
Only bounded, live incremental projections can enter the existing watchlist alert matcher.
