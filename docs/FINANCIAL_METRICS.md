# Deterministic Financial Metric Dictionary

Formula version: `fundamentals-v1`.

Definitions are version-controlled in Python. The database stores values with formula version,
period basis and input report IDs; it is not a runtime-editable formula registry.

## Period rules

- YoY compares the same fiscal period and statement scope.
- Q2 = H1 - Q1, Q3 standalone = Q3 cumulative - H1, Q4 = FY - Q3 cumulative.
- Derived standalone quarters are labelled `standalone`; balance-sheet facts are never differenced.
- Three-year CAGR uses FY(t-3) to FY(t), requiring four annual endpoints and positive endpoints.
- ROE/ROA use complete-year profit and average opening/closing equity or assets.

## Implemented metrics

| Dimension     | Metrics                                                                                |
| ------------- | -------------------------------------------------------------------------------------- |
| Growth        | Revenue YoY, parent net-profit YoY, derived standalone-quarter YoY, three-year FY CAGR |
| Profitability | Gross margin, parent net margin, FY average-equity ROE, FY average-asset ROA           |
| Quality       | Operating cash flow, OCF/parent profit, receivables YoY, inventory YoY, free cash flow |
| Balance       | Debt/assets, cash, interest-bearing debt, net debt, current ratio, goodwill/assets     |
| Valuation     | Provider PE-TTM, PB, PCF, market cap, three-year positive PE/PB percentiles            |

Metric states are `available`, `missing_input`, `insufficient_history`, `not_applicable`, or
`invalid_input`. Provider failures belong to `data_sync_runs`, not to individual metric states.

ROIC, PEG, EV/EBITDA, PS-TTM, mandatory five-year percentiles, industry comparison, and full bank
metrics are intentionally deferred until their inputs and applicability contracts are stable.
