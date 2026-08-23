from datetime import UTC, date, datetime
from decimal import Decimal
from typing import cast
from uuid import uuid4

import pytest
from zhaoniu_api.comparisons.models import (
    ComparisonAIResearchV1,
    ComparisonCitedText,
    ComparisonCompany,
    ComparisonMetric,
    ComparisonSnapshotDocument,
    ComparisonValue,
)
from zhaoniu_api.comparisons.service import ComparisonService, _decimal, _evidence_id
from zhaoniu_api.db import FundamentalMetricPointRecord


def _point(
    *, period: date, basis: str = "ttm", unit: str = "percent"
) -> FundamentalMetricPointRecord:
    return FundamentalMetricPointRecord(
        id=uuid4(),
        symbol="600519.SH",
        code="roe",
        value=Decimal("12.34000000"),
        unit=unit,
        status="available",
        period_end=period,
        fiscal_period="FY",
        basis=basis,
        known_at=datetime(2026, 8, 1, tzinfo=UTC),
        metric_version="metric-v1",
        input_fingerprint="a" * 64,
        input_report_ids={},
        input_valuation_ids={},
        detail={},
    )


def test_evidence_id_and_decimal_output_are_stable() -> None:
    source_id = uuid4()
    assert _evidence_id("left", "metric", source_id) == _evidence_id("left", "metric", source_id)
    assert _evidence_id("left", "metric", source_id).startswith("EV-")
    assert _decimal(Decimal("12.34000000")) == "12.34"


def test_metric_matching_requires_period_basis_unit_and_version() -> None:
    service = object.__new__(ComparisonService)
    left = [_point(period=date(2025, 12, 31)), _point(period=date(2024, 12, 31))]
    right = [
        _point(period=date(2025, 12, 31), basis="single_quarter"),
        _point(period=date(2024, 12, 31)),
    ]
    matched_left, matched_right = service._latest_comparable(left, right)
    assert matched_left is not None and matched_right is not None
    assert matched_left.period_end == matched_right.period_end == date(2024, 12, 31)


@pytest.mark.parametrize("text", ["建议买入", "甲公司更好", "增长百分之十"])
def test_ai_comparison_rejects_advice_ranking_and_numbers(text: str) -> None:
    evidence_id = "EV-AAAAAAAAAAAA"
    cited = ComparisonCitedText(text=text, evidence_refs=[evidence_id])
    document = ComparisonAIResearchV1(
        headline=cited,
        common_ground=[cited],
        differences=[cited],
        attention_items=[],
    )
    with pytest.raises(ValueError):
        ComparisonService._validate_ai(document, {evidence_id})


def test_ai_comparison_rejects_unknown_evidence() -> None:
    cited = ComparisonCitedText(text="两侧的证据口径存在差异", evidence_refs=["EV-UNKNOWN00000"])
    document = ComparisonAIResearchV1(
        headline=cited,
        common_ground=[cited],
        differences=[cited],
        attention_items=[],
    )
    with pytest.raises(ValueError, match="invalid_evidence_reference"):
        ComparisonService._validate_ai(document, set())


def test_ai_context_uses_deterministic_relations_without_numeric_values() -> None:
    document = ComparisonSnapshotDocument(
        knowledge_cutoff=datetime(2026, 8, 23, tzinfo=UTC),
        left=ComparisonCompany(
            symbol="600519.SH",
            ticker="600519",
            name="贵州茅台",
            exchange="SSE",
            board="main",
        ),
        right=ComparisonCompany(
            symbol="300750.SZ",
            ticker="300750",
            name="宁德时代",
            exchange="SZSE",
            board="chinext",
        ),
        same_industry=False,
        metrics=[
            ComparisonMetric(
                code="gross_margin",
                label="毛利率",
                dimension="盈利能力",
                comparability="comparable",
                left=ComparisonValue(
                    value="89.55",
                    unit="percent",
                    status="available",
                    evidence_ref="EV-LEFT0000000",
                ),
                right=ComparisonValue(
                    value="23.92",
                    unit="percent",
                    status="available",
                    evidence_ref="EV-RIGHT000000",
                ),
            )
        ],
        recent_signals=[],
        limitations=[],
    )
    context = ComparisonService._ai_context(document)
    serialized = str(context)
    metrics = cast(list[dict[str, object]], context["metrics"])
    assert metrics[0]["relation"] == "left_higher"
    assert "89.55" not in serialized
    assert "23.92" not in serialized
    assert "600519" not in serialized
