# Event Taxonomy

The registry supports six families after Phase 16:

| Family                   | Event types                                                                                                    |
| ------------------------ | -------------------------------------------------------------------------------------------------------------- |
| `share_repurchase`       | plan, progress, completed, adjusted, cancelled                                                                 |
| `share_pledge`           | created, released, changed                                                                                     |
| `share_unlock`           | scheduled, completed                                                                                           |
| `regulatory_action`      | inquiry, investigation opened, warning letter, administrative penalty, disciplinary action, regulatory measure |
| `shareholder_change`     | plan, progress, completed, cancelled; direction is explicitly increase or decrease                             |
| `litigation_arbitration` | filed, progress, judgment or award, closed                                                                     |

Titles are classified by ordered, versioned rules. Multiple family matches are `ambiguous` and are
withheld. Major contracts, executive changes and news-derived events remain deferred. V2 families
use standalone document threads when a holder/plan or case identity cannot be established reliably.
