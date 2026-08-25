# Controlled Beta release gate

Phase 12 supports an invitation-only controlled Beta, not an unrestricted public launch. Run:

```text
uv run python -m zhaoniu_api.cli check-beta-readiness
```

The gate checks invitation mode, user capacity, transactional email, legal review, data-use review
and commercialization prerequisites. A non-ready result is an intentional release block and must
not be bypassed with fabricated approvals. Operators issue invitations and advanced-access codes
out of band; the UI contains no checkout, price or payment representation.

Before release: build both containers, migrate a production-like database, run all quality checks,
complete a backup/restore drill, verify desktop/mobile registration and recovery, and confirm
`/readyz`. Record the deployed commit and migration head in the release log.

Phase 19 implementation and sign-off evidence is tracked in `docs/PHASE_19_BASELINE.md`. The
internal Phase 19 baseline may record an explicit product-approved scope deferral, but that does
not waive this release gate: transactional email and the real account lanes must pass before an
invited Beta.
