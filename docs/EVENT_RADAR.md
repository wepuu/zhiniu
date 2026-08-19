# Event Radar

The stock research workspace adds a fourth secondary tab, `事件雷达`, after `同行位置`. It does not
add a top-level route or replace deterministic changes.

The read-only API is:

```text
GET /api/v1/stocks/{symbol}/events
GET /api/v1/stocks/{symbol}/events/{event_id}
GET /api/v1/stocks/{symbol}/event-radar
```

The radar separates recent disclosures from upcoming effective events. Its envelope exposes
`ready`, `no_events`, `not_built`, `building`, and `failed`, plus freshness, source health and
coverage. A source or radar failure is isolated from fundamental, peer and AI research queries.

Desktop opens evidence in a side sheet. Mobile uses the same accessible dialog as a bottom sheet.
Both views show source owner, source publication time, knowledge time and a link to the retained
source document.
