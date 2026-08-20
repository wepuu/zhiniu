from decimal import Decimal

from zhaoniu_api.screening.models import MetricCriterion, ScreenQuery
from zhaoniu_api.screening.service import ScreeningService, _compare


def _query(*, selector: str = "latest_available", metric: str = "gross_margin") -> ScreenQuery:
    return ScreenQuery.model_validate(
        {
            "filters": [
                {
                    "kind": "metric",
                    "metric_code": metric,
                    "selector": selector,
                    "operator": "gte",
                    "value": "30.00",
                }
            ]
        }
    )


def test_screen_query_hash_is_stable_for_decimal_input() -> None:
    service = ScreeningService(None)  # type: ignore[arg-type]
    first = service.validate(_query())
    second = service.validate(_query())

    assert first.valid
    assert first.query_hash == second.query_hash
    assert first.canonical_query is not None
    criterion = first.canonical_query.filters[0]
    assert isinstance(criterion, MetricCriterion)
    assert criterion.value == Decimal("30.00")


def test_screen_validation_rejects_unknown_metric_and_invalid_selector() -> None:
    service = ScreeningService(None)  # type: ignore[arg-type]

    unknown = service.validate(_query(metric="future_alpha_score"))
    invalid_selector = service.validate(_query(selector="latest_fy"))

    assert not unknown.valid
    assert unknown.issues[0].code == "unsupported_metric"
    assert not invalid_selector.valid
    assert invalid_selector.issues[0].code == "unsupported_selector"


def test_between_comparison_is_inclusive_and_requires_both_bounds() -> None:
    assert _compare(Decimal("10"), "between", Decimal("10"), Decimal("20"))
    assert _compare(Decimal("20"), "between", Decimal("10"), Decimal("20"))
    assert not _compare(Decimal("21"), "between", Decimal("10"), Decimal("20"))
    assert not _compare(Decimal("15"), "between", Decimal("10"), None)
