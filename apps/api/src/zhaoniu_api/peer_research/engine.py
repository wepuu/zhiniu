from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from decimal import Decimal

from zhaoniu_api.peer_research.models import (
    ComparableMetricInput,
    PeerBenchmarkResult,
    PeerComparisonStatus,
    PeerMetricKind,
    PeerUniverse,
)

MINIMUM_VALID_SAMPLE_SIZE = 8

METRIC_DIMENSIONS: dict[str, str] = {
    "revenue_yoy": "growth",
    "parent_net_profit_yoy": "growth",
    "revenue_cagr_3y": "growth",
    "net_profit_cagr_3y": "growth",
    "gross_margin": "profitability",
    "parent_net_margin": "profitability",
    "roe": "profitability",
    "roa": "profitability",
    "ocf_to_parent_profit": "quality",
    "accounts_receivable_yoy": "quality",
    "inventory_yoy": "quality",
    "free_cash_flow": "quality",
    "debt_to_assets": "balance",
    "current_ratio": "balance",
    "goodwill_to_assets": "balance",
    "interest_bearing_debt": "balance",
    "net_debt": "balance",
    "pe_ttm": "valuation",
    "pb": "valuation",
    "pcf": "valuation",
    "market_cap": "valuation",
}

FUNDAMENTAL_CODES = tuple(
    code for code, dimension in METRIC_DIMENSIONS.items() if dimension != "valuation"
)
VALUATION_CODES = ("pe_ttm", "pb", "pcf", "market_cap")


def percentile_rank(values: list[Decimal], target: Decimal) -> Decimal:
    count_less = sum(1 for item in values if item < target)
    count_equal = sum(1 for item in values if item == target)
    return (Decimal(count_less) + Decimal("0.5") * Decimal(count_equal)) / Decimal(
        len(values)
    ) * Decimal("100")


def numeric_rank_desc(values: list[Decimal], target: Decimal) -> int:
    return 1 + sum(1 for item in values if item > target)


def quantile(values: list[Decimal], q: Decimal) -> Decimal:
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = q * Decimal(len(ordered) - 1)
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - Decimal(lower)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def latest_by_metric(inputs: list[ComparableMetricInput]) -> dict[str, ComparableMetricInput]:
    grouped: dict[str, list[ComparableMetricInput]] = defaultdict(list)
    for item in inputs:
        grouped[item.metric_code].append(item)
    result: dict[str, ComparableMetricInput] = {}
    for code, rows in grouped.items():
        result[code] = max(
            rows,
            key=lambda item: (
                item.period_end is not None,
                item.period_end,
                item.known_at or datetime.min,
                item.source_id.hex,
            ),
        )
    return result


def compare_metric(
    metric_code: str,
    metric_kind: PeerMetricKind,
    company: ComparableMetricInput | None,
    peer_inputs: list[ComparableMetricInput],
    *,
    minimum_sample_size: int = MINIMUM_VALID_SAMPLE_SIZE,
) -> PeerBenchmarkResult:
    if company is None:
        return PeerBenchmarkResult(
            metric_code=metric_code,
            metric_kind=metric_kind,
            status=PeerComparisonStatus.MISSING_METRIC,
            company_input=None,
            peer_inputs=(),
            reason="target_metric_missing",
        )
    comparable: list[ComparableMetricInput] = []
    excluded_invalid = 0
    for item in peer_inputs:
        if not _is_same_comparable_basis(company, item):
            continue
        if metric_code == "pe_ttm" and item.value <= 0:
            excluded_invalid += 1
            continue
        comparable.append(item)
    if metric_code == "pe_ttm" and company.value <= 0:
        return PeerBenchmarkResult(
            metric_code=metric_code,
            metric_kind=metric_kind,
            status=PeerComparisonStatus.INVALID_INPUTS,
            company_input=company,
            peer_inputs=tuple(comparable),
            excluded_invalid_value_count=excluded_invalid,
            reason="target_pe_not_positive",
        )
    if len(comparable) < minimum_sample_size:
        return PeerBenchmarkResult(
            metric_code=metric_code,
            metric_kind=metric_kind,
            status=PeerComparisonStatus.INSUFFICIENT_PEERS,
            company_input=company,
            peer_inputs=tuple(comparable),
            sample_size=len(comparable),
            excluded_invalid_value_count=excluded_invalid,
            reason="minimum_peer_sample_not_met",
        )
    values = [item.value for item in comparable]
    all_values = values + [company.value]
    return PeerBenchmarkResult(
        metric_code=metric_code,
        metric_kind=metric_kind,
        status=PeerComparisonStatus.AVAILABLE,
        company_input=company,
        peer_inputs=tuple(comparable),
        median=quantile(values, Decimal("0.5")),
        p25=quantile(values, Decimal("0.25")),
        p75=quantile(values, Decimal("0.75")),
        numeric_percentile=percentile_rank(all_values, company.value),
        numeric_rank_desc=numeric_rank_desc(all_values, company.value),
        sample_size=len(comparable),
        excluded_invalid_value_count=excluded_invalid,
    )


def _is_same_comparable_basis(company: ComparableMetricInput, peer: ComparableMetricInput) -> bool:
    return (
        peer.metric_code == company.metric_code
        and peer.metric_version == company.metric_version
        and peer.unit == company.unit
        and peer.basis == company.basis
        and peer.period_end == company.period_end
        and peer.fiscal_period == company.fiscal_period
    )


def universe_status(universe: PeerUniverse) -> PeerComparisonStatus:
    if universe.status != PeerComparisonStatus.AVAILABLE:
        return universe.status
    if len(universe.peer_symbols) < MINIMUM_VALID_SAMPLE_SIZE:
        return PeerComparisonStatus.INSUFFICIENT_PEERS
    return PeerComparisonStatus.AVAILABLE

