# Licensed A-share Provider Acceptance

This is the Phase 25G decision record template for an invited-Beta data source. Completing a
technical adapter or a healthy diagnostic does not approve commercial use. Product/legal owners
must retain the signed source terms and the engineering acceptance run must reference the exact
configuration revision.

## Dataset decision matrix

Record one explicit decision for every dataset; different Providers may be selected.

| Dataset              | Required point-in-time semantics                                               | Required rights and operations evidence                    |
| -------------------- | ------------------------------------------------------------------------------ | ---------------------------------------------------------- |
| Stock master         | listing, delisting, exchange, board and identifier history                     | display, cache, redistribution, update SLA                 |
| Trading calendar     | SSE/SZSE sessions and exceptional closures                                     | source version, publication time, Hong Kong access         |
| Daily market         | unadjusted OHLC, shares volume, amount, suspension and corporate-action inputs | history depth, burst/quota, display and retention          |
| Financial statements | report period, announcement/known time, revision, audit and consolidated basis | historical revisions, derived-metric and AI-context rights |
| Valuation            | metric code, basis, unit, observation and known time                           | cache/display rights and reproducible historical depth     |
| Industry             | taxonomy source/version and membership effective time                          | attribution, redistribution and version retention          |
| Disclosures          | exchange/CNInfo identity, publication time, URL and document retention         | metadata/document rights, outage and deletion terms        |

For every accepted source, attach the contract or approval reference, permitted environments,
attribution copy, retention/deletion obligation, rate limits, outage escalation and termination
procedure. `legal_review_status` and `data_use_status` alone are not substitutes for this record.

## Engineering acceptance

1. Implement only through Provider -> Normalizer -> Canonical Model -> Repository.
2. Store a distinct Provider identity and configuration revision; never overwrite evaluation-source
   lineage or silently merge rows from two sources.
3. Run the licensed adapter alongside the evaluation adapter in acceptance mode.
4. Verify units, identifiers, knowledge time, revisions, idempotency, bounded retries and redacted
   failures with retained payload fingerprints.
5. Run the exact fixed sample set:
   - `600519.SH`: SSE main-board market, financial, valuation and AI evidence chain.
   - `300750.SZ`: ChiNext, industry membership and peer research.
   - `300376.SZ`: disclosure and event-radar chain.
   - `000001.SZ`: bank issuer template and honest unsupported dimensions.
6. Exercise quota exhaustion, timeout, malformed payload, revision and provider-unavailable paths.
7. Bind the passing Phase 20 acceptance run to the same environment, Provider revision and release
   candidate used by Phase 21/22 gates.

## Admission decision

External invitations remain blocked unless every mandatory dataset has an approved decision, the
fixed-sample acceptance is current and Beta-eligible, and the current 48-hour reliability evidence
passes. AKShare, Sina and the current Baidu evaluation endpoint remain suitable only for
`development_evaluation`; their technical availability cannot be recorded as commercial approval.
