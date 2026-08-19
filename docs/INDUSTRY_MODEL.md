# Industry Model

Phase 6 makes industry classification a first-class domain instead of relying on
`stocks.industry_code` as free text.

## Phase 6 taxonomy

The implemented taxonomy is:

```text
akshare_dev_industry / phase6-dev-v1
```

It imports the industry field that already exists in the Phase 1 stock master when populated. If a
local development database has no populated industry field, the importer can add a very small
`phase6_dev_seed` for explicit acceptance symbols. This is a development and technical-validation
taxonomy only. It is not a production licensed industry classification. Commercial display,
redistribution, provider attribution and stability remain `TBD / requires legal review`.

The intended production replacement is one explicitly licensed or official classification source,
such as an official CSRC/CAPCO listed-company industry classification result, after the source,
machine-ingestion path and reuse terms are confirmed.

## Entities

- `industry_taxonomies`: taxonomy code, version, source reference and licensing status.
- `industries`: taxonomy-scoped industry nodes.
- `industry_memberships`: stock-to-industry membership with `known_at`, validity window and
  lineage hash.

Membership rows are versioned. A later industry change creates another membership row; historical
benchmark snapshots are not rewritten.

## Peer universe

Phase 6 resolves peers deterministically:

```text
same taxonomy
same taxonomy version
same finest available industry
same issuer/research template
listed stocks only
membership.known_at <= knowledge_cutoff
```

LLMs must not select peer companies. Banks and other unsupported issuer templates do not fall back
to general industrial-company peer rules.
