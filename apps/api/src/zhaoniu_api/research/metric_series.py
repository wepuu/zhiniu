import hashlib
import json
from datetime import timedelta
from decimal import Decimal
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from zhaoniu_api.fundamentals.metrics import (
    DEFINITION_BY_CODE,
    METRIC_VERSION,
    compute_fundamental_metrics,
)
from zhaoniu_api.fundamentals.models import (
    FinancialReport,
    MetricBasis,
    MetricStatus,
    ValuationObservation,
)
from zhaoniu_api.research.models import FundamentalMetricPoint


def _hash(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _point_id(fingerprint: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"zhaoniu:metric-point:{fingerprint}")


def build_financial_metric_points(
    reports: list[FinancialReport],
) -> tuple[FundamentalMetricPoint, ...]:
    ordered = sorted(reports, key=lambda item: (item.period_end, item.known_at))
    report_by_id = {item.id: item for item in ordered}
    points: list[FundamentalMetricPoint] = []
    seen: set[tuple[str, object, object, str]] = set()
    for index, report in enumerate(ordered):
        metrics = compute_fundamental_metrics(ordered[: index + 1])
        for metric in metrics:
            if metric.period_end != report.period_end:
                continue
            identity = (metric.code, metric.period_end, metric.basis, report.payload_checksum)
            if identity in seen:
                continue
            seen.add(identity)
            inputs = tuple(dict.fromkeys(metric.input_report_ids))
            material = {
                "symbol": report.canonical_symbol,
                "code": metric.code,
                "period_end": report.period_end.isoformat(),
                "basis": metric.basis,
                "metric_version": METRIC_VERSION,
                "inputs": [
                    {
                        "id": str(item_id),
                        "checksum": report_by_id[item_id].payload_checksum,
                    }
                    for item_id in inputs
                    if item_id in report_by_id
                ],
                "value": str(metric.value) if metric.value is not None else None,
                "status": metric.status,
            }
            fingerprint = _hash(material)
            known_times = [
                report_by_id[item_id].known_at for item_id in inputs if item_id in report_by_id
            ]
            points.append(
                FundamentalMetricPoint(
                    id=_point_id(fingerprint),
                    canonical_symbol=report.canonical_symbol,
                    code=metric.code,
                    value=metric.value,
                    unit=metric.unit,
                    status=metric.status,
                    period_end=report.period_end,
                    fiscal_period=report.fiscal_period,
                    basis=metric.basis,
                    known_at=max(known_times, default=report.known_at),
                    metric_version=METRIC_VERSION,
                    input_fingerprint=fingerprint,
                    input_report_ids=inputs,
                    detail={"note": metric.detail} if metric.detail else {},
                )
            )
    return tuple(points)


def _percentile(values: list[Decimal], current: Decimal) -> Decimal:
    count = sum(1 for value in values if value <= current)
    return (Decimal(count) / Decimal(len(values)) * Decimal("100")).quantize(Decimal("0.0001"))


def build_valuation_metric_points(
    observations: list[ValuationObservation],
) -> tuple[FundamentalMetricPoint, ...]:
    points: list[FundamentalMetricPoint] = []
    for source_code, metric_code in (
        ("pe_ttm", "pe_ttm_percentile_3y"),
        ("pb", "pb_percentile_3y"),
    ):
        values = sorted(
            (item for item in observations if item.metric_code == source_code and item.value > 0),
            key=lambda item: item.trade_date,
        )
        for endpoint in values[-2:]:
            window_start = endpoint.trade_date - timedelta(days=365 * 3)
            window = [
                item for item in values if window_start <= item.trade_date <= endpoint.trade_date
            ]
            span_days = (
                (window[-1].trade_date - window[0].trade_date).days if len(window) > 1 else 0
            )
            valid = len(window) >= 500 and span_days >= 900
            value = _percentile([item.value for item in window], endpoint.value) if valid else None
            status = MetricStatus.AVAILABLE if valid else MetricStatus.INSUFFICIENT_HISTORY
            detail: dict[str, Any] = {
                "source_metric": source_code,
                "current_multiple": str(endpoint.value),
                "sample_count": len(window),
                "window_start": window[0].trade_date.isoformat() if window else None,
                "window_end": endpoint.trade_date.isoformat(),
                "provider": endpoint.provider,
            }
            material = {
                "symbol": endpoint.canonical_symbol,
                "code": metric_code,
                "period_end": endpoint.trade_date.isoformat(),
                "metric_version": METRIC_VERSION,
                "endpoint_id": str(endpoint.id),
                "endpoint_value": str(endpoint.value),
                "sample_count": len(window),
                "window_start": detail["window_start"],
                "value": str(value) if value is not None else None,
            }
            fingerprint = _hash(material)
            points.append(
                FundamentalMetricPoint(
                    id=_point_id(fingerprint),
                    canonical_symbol=endpoint.canonical_symbol,
                    code=metric_code,
                    value=value,
                    unit=DEFINITION_BY_CODE[metric_code].unit,
                    status=status,
                    period_end=endpoint.trade_date,
                    fiscal_period="market",
                    basis=MetricBasis.POINT_IN_TIME,
                    known_at=endpoint.collected_at,
                    metric_version=METRIC_VERSION,
                    input_fingerprint=fingerprint,
                    input_valuation_ids=(endpoint.id,),
                    detail=detail,
                )
            )
    return tuple(points)
