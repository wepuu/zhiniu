# Event Attention Rules

Attention is a radar-snapshot property, never an intrinsic event field. V1 has three neutral levels:

- `important`: investigations, administrative penalties and disciplinary actions.
- `notice`: inquiries, warning letters, regulatory measures, pledge creation/change, scheduled
  unlocks and cancelled repurchases.
- `info`: routine repurchase progress/completion, pledge release and completed unlocks.

Every item stores the rule ID, rule version and a research-oriented reason. The levels organize what
to verify next; they do not express good/bad, buy/sell, expected return, price target, probability or
personalized advice.

Phase 16 shareholder plans/progress and case filings/progress/judgments default to `notice`.
Completed or cancelled shareholder changes and closed cases default to `info`. No ratio or amount
threshold is introduced without validated units, real fixtures and a separately versioned rule.
