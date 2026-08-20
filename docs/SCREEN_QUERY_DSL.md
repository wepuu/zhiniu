# Screen Query DSL v1

`screen-query-v1` is a closed, versioned JSON contract. Unknown fields and unsupported codes are
rejected. All filters are combined with AND and a query must contain one to eight filters.

```json
{
  "dsl_version": "screen-query-v1",
  "filters": [
    {
      "kind": "metric",
      "metric_code": "roe_avg_equity_fy",
      "selector": "latest_fy",
      "operator": "gte",
      "value": "15"
    },
    {
      "kind": "event",
      "event_family": "regulatory_action",
      "mode": "not_exists",
      "within_days": 365
    }
  ],
  "sort": { "field": "symbol", "direction": "asc" }
}
```

## Criteria

- `metric`: allow-listed fundamental metric or valuation observation. Decimal values are strings in
  the API. `latest_fy` is limited to explicitly annual metrics.
- `peer`: allow-listed metric percentile from an immutable peer benchmark, bounded to 0–100.
- `industry`: one or more codes from the exact taxonomy code and version exposed by the catalog.
- `event`: existence or verified absence of a supported event family within 1–730 days.

Operators are `gt`, `gte`, `lt`, `lte`, and inclusive `between`. `upper_value` is required only for
`between`. Units are defined by the catalog rather than accepted from the caller. Supported metric,
industry, peer and event codes must be discovered from `GET /api/v1/screens/catalog`.

## HTTP workflow

```text
GET  /api/v1/screens/catalog
GET  /api/v1/screens/coverage
POST /api/v1/screens/validate
POST /api/v1/screens/executions
GET  /api/v1/screens/executions/{id}
GET  /api/v1/screens/executions/{id}/results
```

Validation is public and side-effect free. Execution and result reads require a session; creation is
also protected by CSRF and allowed-Origin checks. Results use an opaque deterministic cursor.
