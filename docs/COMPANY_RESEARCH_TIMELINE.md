# Company Research Timeline

The company timeline is a read-only company-level view over retained `research_signals`. It is not
a fourth research-fact domain and has no build table or worker. Fundamental observations, peer
position observations and immutable corporate-event versions remain authoritative.

`GET /api/v1/stocks/{symbol}/timeline` freezes a `query_cutoff` on the first page and orders rows by
`known_at DESC, id DESC`. The opaque cursor binds the cutoff, position and filter hash. Upcoming
events are hydrated separately from the latest eligible event-radar snapshot and ordered by their
effective date; they never replace disclosure-time ordering.

Timeline items retain exactly one source artifact and route evidence back to the existing Phase 3,
6 or 7 API. AI output is not a timeline fact. Event versions are not collapsed in the timeline;
the event radar still exposes the latest version per thread at its point-in-time cutoff.

Historical and replay projections may populate the timeline but set `alert_eligible=false`.
Only bounded, live incremental projections can enter the existing watchlist alert matcher.
