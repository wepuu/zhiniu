# Event Taxonomy

Phase 7 V1 deliberately supports four families:

| Family              | Event types                                                                                                    |
| ------------------- | -------------------------------------------------------------------------------------------------------------- |
| `share_repurchase`  | plan, progress, completed, adjusted, cancelled                                                                 |
| `share_pledge`      | created, released, changed                                                                                     |
| `share_unlock`      | scheduled, completed                                                                                           |
| `regulatory_action` | inquiry, investigation opened, warning letter, administrative penalty, disciplinary action, regulatory measure |

Titles are classified by ordered, versioned rules. Multiple family/type matches are `ambiguous` and
are withheld. Shareholder changes, litigation, major contracts, executive changes and news-derived
events are deferred until their identity, source and extraction contracts are separately defined.
