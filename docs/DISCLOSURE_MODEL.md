# Disclosure Model

Phase 7 treats a disclosure document as evidence, not as an event. `disclosure_documents` stores
the source owner, source document identity, title, URL and four distinct time concepts:

- `source_published_at` is the timestamp stated by the source.
- `source_published_precision` records whether that value is a date or a timestamp.
- `known_at` is the earliest conservative research cutoff at which the document may be used.
- `ingested_at` is when Zhaoniu observed the record.

For date-only disclosures, `known_at` is the next China-calendar day at 00:00 Asia/Shanghai. This
prevents a snapshot from using a disclosure before its publication day has completed.

AKShare is an adapter used for development evaluation. The record owner remains CNInfo,
Eastmoney, or Sina. A source URL and source identity must be retained; the product must not label an
AKShare-derived record as a direct official integration.

Classification is deterministic and versioned. A document is `classified`, `unclassified`,
`ambiguous`, or `unsupported`. Ambiguous and unsupported documents do not become public events.
