# AI Stock Health Research

Phase 4 produces one evidence-bound `StockHealthResearchV1` document from an immutable Phase 3
research snapshot. It is research commentary, not a score, prediction, target price, recommendation
or personalized securities advice.

## Deterministic boundary

`AIContextBuilder` is the only input path. It selects at most five observations by attention level,
dimension diversity, current period and stable key. Every selected observation receives a stable
`EV-` identifier derived from its snapshot, observation, metric-point and source identities. The
canonical JSON context and its hash are stored with the run identity.

The model sees stock identity, cutoff, coverage, selected evidence, units, calculation traces and
source identities. It never receives provider payloads, database rows, user data or secrets. Data
limitations and unsupported issuer types are produced by deterministic code before any model call.

## Fail-closed output

The structured response is accepted only after Pydantic schema, citation, dimension/coverage,
numeric-claim and investment-language validation. Every prose field has one to four valid evidence
references. AI prose cannot contain financial numbers, percentages, dates, currency values or price
targets; UI number cards come from the persisted evidence index.

If a provider call, parsing or safety validation fails, orchestration advances to the next configured
model within the total attempt and deadline budget. Context, database and unknown application errors
terminate immediately. A complete failure stores no output.

## Operations

No model is enabled by default. Configure an ordered route and independent provider credentials,
then run the CLI or Celery task. Successful equivalent work is returned as `skipped`; a failed run
requires `--retry-failed`. Public HTTP endpoints are read-only.

```text
uv run python -m zhaoniu_api.cli generate-ai-stock-health 600519
uv run python -m zhaoniu_api.cli generate-ai-stock-health 600519 --retry-failed
```

The stock page always labels generated content, identifies the actual provider/model and generation
cutoff, and preserves direct evidence navigation. Older valid outputs remain readable and are marked
`stale` when a newer deterministic research snapshot exists.
