# Corporate Event Engine

The event engine is a deterministic application module under
`apps/api/src/zhaoniu_api/corporate_events`. Data flows through:

```text
Provider -> Raw DTO -> Normalizer -> Disclosure / staged fact -> Classifier -> Extractor
         -> Immutable corporate event -> Point-in-time radar snapshot
```

Structured source facts are staged until they can be matched to a disclosure document. A public
event always has at least one `corporate_event_inputs` link to source evidence. Extraction status is
`complete`, `partial`, or `invalid`; invalid candidates are never published.

`event_thread_key` groups legal versions of one event thread. `event_version_fingerprint` makes each
immutable version idempotent. `previous_event_id` provides explicit version lineage. Radar builds
select the latest known version in each thread at the requested cutoff.

CLI and Celery call the same application service. Provider retries are limited to transient
provider errors; classification, validation, database, and unknown application errors fail closed.
