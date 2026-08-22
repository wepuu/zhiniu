# Event Engine V2

Phase 16 adds `shareholder_change` and `litigation_arbitration` to the existing deterministic event
engine. Classification is ordered and versioned. Exclusion rules withhold ambiguous disclosures;
an LLM is never an authoritative extractor.

Shareholder-change V1 supports plan, progress, completed and cancelled stages with an explicit
increase/decrease direction. Litigation/arbitration V1 supports filed, progress, judgment/award and
closed stages. Missing holder, amount, case reference or counterparty fields remain null.

Structured facts may be attached only by an exact retained source-document identity. Publication
date proximity is not sufficient. A reliable holder/plan reference or case reference may link
versions into a thread. Otherwise the disclosure receives a standalone thread. This deliberately
prefers under-linking to combining unrelated shareholders, plans or cases.

New-family attention remains neutral and conservative. No event becomes positive/negative, a stock
score, a recommendation or a forecast. Cross-domain ratios such as litigation amount to revenue
remain deferred until their financial input, basis, cutoff and evidence contracts are defined.
