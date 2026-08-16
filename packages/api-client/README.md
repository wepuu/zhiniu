# API client

`openapi.json` is generated from FastAPI with `uv run python scripts/export_openapi.py`. Phase 1 should add a pinned generator and make generated types the only web/API contract source. Do not hand-maintain a parallel set of large TypeScript response types.
