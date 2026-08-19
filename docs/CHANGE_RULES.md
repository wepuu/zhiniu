# Deterministic Change Rules

Rule engine version: `change-engine-v1`. The rule-set version is a deterministic digest of all
enabled rule IDs, versions, required metrics and thresholds. Rules produce research observations;
they do not produce recommendations, target prices or return forecasts.

## Phase 3 rule families

| Dimension     | Rule                                  | Trigger semantics                                                                          |
| ------------- | ------------------------------------- | ------------------------------------------------------------------------------------------ |
| Growth        | Revenue single-quarter momentum       | Three consecutive fiscal quarters are required; two points never imply “continuous” change |
| Growth        | Parent-profit single-quarter momentum | Same three-point rule; crossing zero takes priority over a generic momentum card           |
| Profitability | Gross-margin change                   | Latest value versus the same fiscal period in the prior year                               |
| Profitability | Parent-net-margin change              | Latest value versus the same fiscal period in the prior year                               |
| Quality       | OCF versus profit growth gap          | Percentage-point gap; important level at 35pp                                              |
| Quality       | Receivables versus revenue gap        | Trigger at an inclusive 20pp gap                                                           |
| Quality       | Inventory versus revenue gap          | Trigger at an inclusive 20pp gap                                                           |
| Balance       | Debt/assets change                    | Latest value versus the same fiscal period in the prior year                               |
| Valuation     | PE three-year percentile band         | Positive observations only; at least 500 samples and 900 calendar days                     |
| Valuation     | PB three-year percentile band         | Distinguishes “currently in band” from “just crossed threshold”                            |

General-enterprise rules are not applied to banks or unsupported issuer types. Missing or
insufficient inputs produce coverage states rather than fabricated observations. Industry-relative
rules, event rules, episode lifecycle and bank-specific rules are deferred.

Each observation stores the rule ID/version, content fingerprint, comparison periods, calculation
expression and referenced metric points. The LLM boundary is not involved.

## Phase 6 peer-position observations

Phase 6 may surface a small number of deterministic peer-position observations from stored peer
benchmark results:

- value materially above peer median;
- value materially below peer median;
- value in a high numeric peer percentile;
- value in a low numeric peer percentile.

These thresholds are attention heuristics only. They are not investment-quality judgments and must
not be phrased as buy/sell, good/bad, leading/lagging, bullish/bearish or target-price language.
