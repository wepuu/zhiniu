import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import NAMESPACE_URL, UUID, uuid5

from zhaoniu_api.fundamentals.metrics import DEFINITION_BY_CODE
from zhaoniu_api.fundamentals.models import FinancialReport, MetricStatus
from zhaoniu_api.research.models import (
    AttentionLevel,
    CalculationTrace,
    EvidenceMetric,
    EvidenceSource,
    FundamentalMetricPoint,
    Movement,
    ObservationDimension,
    ResearchObservation,
)

RULE_ENGINE_VERSION = "change-engine-v1"


@dataclass(frozen=True, slots=True)
class ChangeRuleDefinition:
    rule_id: str
    version: str
    dimension: ObservationDimension
    required_metrics: tuple[str, ...]
    minimum_history: int
    parameters: dict[str, str]
    supported_templates: tuple[str, ...] = ("fundamental_general:v1",)


RULES = (
    ChangeRuleDefinition(
        "growth.revenue_single_quarter_momentum",
        "v1",
        ObservationDimension.GROWTH,
        ("revenue_single_quarter_yoy",),
        3,
        {"min_step_pp": "1", "min_total_pp": "3", "zero_band_pp": "1"},
    ),
    ChangeRuleDefinition(
        "growth.parent_profit_single_quarter_momentum",
        "v1",
        ObservationDimension.GROWTH,
        ("parent_net_profit_single_quarter_yoy",),
        3,
        {"min_step_pp": "1", "min_total_pp": "3", "zero_band_pp": "1"},
    ),
    ChangeRuleDefinition(
        "profitability.gross_margin_yoy_delta",
        "v1",
        ObservationDimension.PROFITABILITY,
        ("gross_margin",),
        2,
        {"threshold_pp": "2"},
    ),
    ChangeRuleDefinition(
        "profitability.parent_net_margin_yoy_delta",
        "v1",
        ObservationDimension.PROFITABILITY,
        ("parent_net_margin",),
        2,
        {"threshold_pp": "2"},
    ),
    ChangeRuleDefinition(
        "quality.ocf_profit_growth_gap",
        "v1",
        ObservationDimension.QUALITY,
        ("operating_cash_flow_yoy", "parent_net_profit_yoy"),
        1,
        {"threshold_pp": "20", "important_pp": "35"},
    ),
    ChangeRuleDefinition(
        "quality.ar_revenue_growth_gap",
        "v1",
        ObservationDimension.QUALITY,
        ("accounts_receivable_yoy", "revenue_yoy"),
        1,
        {"threshold_pp": "20"},
    ),
    ChangeRuleDefinition(
        "quality.inventory_revenue_growth_gap",
        "v1",
        ObservationDimension.QUALITY,
        ("inventory_yoy", "revenue_yoy"),
        1,
        {"threshold_pp": "20"},
    ),
    ChangeRuleDefinition(
        "balance.debt_asset_yoy_delta",
        "v1",
        ObservationDimension.BALANCE,
        ("debt_to_assets",),
        2,
        {"threshold_pp": "3"},
    ),
    ChangeRuleDefinition(
        "valuation.pe_percentile_band",
        "v1",
        ObservationDimension.VALUATION,
        ("pe_ttm_percentile_3y",),
        1,
        {"high": "80", "low": "20", "minimum_samples": "500"},
    ),
    ChangeRuleDefinition(
        "valuation.pb_percentile_band",
        "v1",
        ObservationDimension.VALUATION,
        ("pb_percentile_3y",),
        1,
        {"high": "80", "low": "20", "minimum_samples": "500"},
    ),
)


def rule_set_version() -> str:
    material = [
        {
            "id": item.rule_id,
            "version": item.version,
            "dimension": item.dimension,
            "required_metrics": item.required_metrics,
            "minimum_history": item.minimum_history,
            "parameters": item.parameters,
            "templates": item.supported_templates,
        }
        for item in RULES
    ]
    digest = hashlib.sha256(
        json.dumps(material, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()[:16]
    return f"rules-v1:{digest}"


def _period_index(point: FundamentalMetricPoint) -> int | None:
    quarter = {"Q1": 1, "H1": 2, "Q3": 3, "FY": 4}.get(point.fiscal_period)
    return point.period_end.year * 4 + quarter if quarter else None


def _available(points: list[FundamentalMetricPoint], code: str) -> list[FundamentalMetricPoint]:
    return sorted(
        (
            item
            for item in points
            if item.code == code
            and item.status == MetricStatus.AVAILABLE
            and item.value is not None
        ),
        key=lambda item: item.period_end,
    )


def _same_period_previous(
    points: list[FundamentalMetricPoint], current: FundamentalMetricPoint
) -> FundamentalMetricPoint | None:
    return next(
        (
            item
            for item in reversed(points)
            if item.period_end.year == current.period_end.year - 1
            and item.fiscal_period == current.fiscal_period
            and item.basis == current.basis
        ),
        None,
    )


def _evidence_metric(point: FundamentalMetricPoint, role: str) -> EvidenceMetric:
    definition = DEFINITION_BY_CODE[point.code]
    return EvidenceMetric(
        metric_point_id=point.id,
        role=role,
        metric_code=point.code,
        display_name=definition.display_name,
        period_end=point.period_end,
        fiscal_period=point.fiscal_period,
        basis=point.basis,
        value=point.value,
        unit=point.unit,
        status=point.status,
        input_report_ids=list(point.input_report_ids),
        input_valuation_ids=list(point.input_valuation_ids),
        detail=point.detail,
    )


def _sources(
    evidence_points: list[FundamentalMetricPoint], reports: dict[UUID, FinancialReport]
) -> list[EvidenceSource]:
    ids: list[UUID] = []
    for point in evidence_points:
        for report_id in point.input_report_ids:
            if report_id not in ids:
                ids.append(report_id)
    return [
        EvidenceSource(
            report_id=report.id,
            provider=report.provider,
            provider_record_id=report.provider_record_id,
            fiscal_period=report.fiscal_period,
            period_end=report.period_end,
            published_at=report.published_at,
            published_at_precision=report.published_at_precision,
            known_at=report.known_at,
        )
        for report_id in ids
        if (report := reports.get(report_id)) is not None
    ]


def _make_observation(
    *,
    symbol: str,
    rule: ChangeRuleDefinition,
    observation_family: str,
    observation_type: str,
    attention_level: AttentionLevel,
    movement: Movement,
    title: str,
    summary: str,
    points: list[tuple[str, FundamentalMetricPoint]],
    reports: dict[UUID, FinancialReport],
    calculation: CalculationTrace,
    generated_at: datetime,
) -> ResearchObservation:
    current = points[0][1]
    key_material = {
        "symbol": symbol,
        "rule_id": rule.rule_id,
        "rule_version": rule.version,
        "family": observation_family,
        "type": observation_type,
        "current_period": current.period_end.isoformat(),
    }
    observation_key = hashlib.sha256(
        json.dumps(key_material, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    content_material = {
        **key_material,
        "inputs": [point.input_fingerprint for _, point in points],
        "dimension": rule.dimension,
        "required_metrics": rule.required_metrics,
        "minimum_history": rule.minimum_history,
        "parameters": rule.parameters,
        "supported_templates": rule.supported_templates,
    }
    content_fingerprint = hashlib.sha256(
        json.dumps(content_material, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    evidence_points = [point for _, point in points]
    return ResearchObservation(
        id=uuid5(NAMESPACE_URL, f"zhaoniu:observation:{content_fingerprint}"),
        symbol=symbol,
        dimension=rule.dimension,
        observation_family=observation_family,
        observation_type=observation_type,
        attention_level=attention_level,
        movement=movement,
        title=title,
        summary=summary,
        current_period=current.period_end,
        comparison_periods=[point.period_end for _, point in points[1:]],
        rule_id=rule.rule_id,
        rule_version=rule.version,
        observation_key=observation_key,
        content_fingerprint=content_fingerprint,
        evidence_metrics=[_evidence_metric(point, role) for role, point in points],
        evidence_sources=_sources(evidence_points, reports),
        calculation=calculation,
        generated_at=generated_at,
    )


def _fmt(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.01'))}"


def _growth_rule(
    rule: ChangeRuleDefinition,
    symbol: str,
    all_points: list[FundamentalMetricPoint],
    reports: dict[UUID, FinancialReport],
    generated_at: datetime,
) -> ResearchObservation | None:
    code = rule.required_metrics[0]
    series = _available(all_points, code)
    if len(series) < 2:
        return None
    current, previous = series[-1], series[-2]
    current_index = _period_index(current)
    previous_index = _period_index(previous)
    if current_index is None or previous_index is None or current_index - previous_index != 1:
        return None
    assert current.value is not None and previous.value is not None
    name = DEFINITION_BY_CODE[code].display_name
    zero_band = Decimal(rule.parameters["zero_band_pp"])
    delta = current.value - previous.value
    if previous.value <= -zero_band and current.value >= zero_band:
        return _make_observation(
            symbol=symbol,
            rule=rule,
            observation_family=f"{code}.momentum",
            observation_type="turned_positive",
            attention_level=AttentionLevel.NOTICE,
            movement=Movement.CROSSED_UP,
            title=f"{name}由负转正",
            summary=f"由 {_fmt(previous.value)}% 变为 {_fmt(current.value)}%。",
            points=[("current", current), ("previous", previous)],
            reports=reports,
            calculation=CalculationTrace(
                method="zero_crossing",
                expression=f"{_fmt(previous.value)}% → {_fmt(current.value)}%",
                change_value=delta,
                change_unit="percentage_point",
            ),
            generated_at=generated_at,
        )
    if previous.value >= zero_band and current.value <= -zero_band:
        return _make_observation(
            symbol=symbol,
            rule=rule,
            observation_family=f"{code}.momentum",
            observation_type="turned_negative",
            attention_level=AttentionLevel.NOTICE,
            movement=Movement.CROSSED_DOWN,
            title=f"{name}由正转负",
            summary=f"由 {_fmt(previous.value)}% 变为 {_fmt(current.value)}%。",
            points=[("current", current), ("previous", previous)],
            reports=reports,
            calculation=CalculationTrace(
                method="zero_crossing",
                expression=f"{_fmt(previous.value)}% → {_fmt(current.value)}%",
                change_value=delta,
                change_unit="percentage_point",
            ),
            generated_at=generated_at,
        )
    if len(series) < 3:
        return None
    earliest = series[-3]
    earliest_index = _period_index(earliest)
    if earliest_index is None or previous_index - earliest_index != 1:
        return None
    assert earliest.value is not None
    first_delta = previous.value - earliest.value
    second_delta = current.value - previous.value
    total = current.value - earliest.value
    min_step = Decimal(rule.parameters["min_step_pp"])
    min_total = Decimal(rule.parameters["min_total_pp"])
    if first_delta >= min_step and second_delta >= min_step and total >= min_total:
        observation_type, movement, word = "consecutive_improvement", Movement.UP, "改善"
    elif first_delta <= -min_step and second_delta <= -min_step and total <= -min_total:
        observation_type, movement, word = "consecutive_deterioration", Movement.DOWN, "下降"
    else:
        return None
    return _make_observation(
        symbol=symbol,
        rule=rule,
        observation_family=f"{code}.momentum",
        observation_type=observation_type,
        attention_level=AttentionLevel.NOTICE,
        movement=movement,
        title=f"{name}连续两个季度{word}",
        summary=(
            f"{_fmt(earliest.value)}% → {_fmt(previous.value)}% → {_fmt(current.value)}%，"
            f"累计变化 {_fmt(total)} 个百分点。"
        ),
        points=[("current", current), ("previous", previous), ("earliest", earliest)],
        reports=reports,
        calculation=CalculationTrace(
            method="consecutive_quarter_delta",
            expression=(
                f"({_fmt(previous.value)} - {_fmt(earliest.value)})pp; "
                f"({_fmt(current.value)} - {_fmt(previous.value)})pp"
            ),
            change_value=total,
            change_unit="percentage_point",
        ),
        generated_at=generated_at,
    )


def _same_period_delta_rule(
    rule: ChangeRuleDefinition,
    symbol: str,
    all_points: list[FundamentalMetricPoint],
    reports: dict[UUID, FinancialReport],
    generated_at: datetime,
) -> ResearchObservation | None:
    code = rule.required_metrics[0]
    series = _available(all_points, code)
    if not series:
        return None
    current = series[-1]
    previous = _same_period_previous(series[:-1], current)
    if previous is None or current.value is None or previous.value is None:
        return None
    delta = current.value - previous.value
    threshold = Decimal(rule.parameters["threshold_pp"])
    if abs(delta) < threshold:
        return None
    name = DEFINITION_BY_CODE[code].display_name
    movement = Movement.UP if delta > 0 else Movement.DOWN
    word = "上升" if delta > 0 else "下降"
    return _make_observation(
        symbol=symbol,
        rule=rule,
        observation_family=f"{code}.same_period_delta",
        observation_type="material_change",
        attention_level=AttentionLevel.NOTICE,
        movement=movement,
        title=f"{name}较上年同期{word}",
        summary=f"{_fmt(previous.value)}% → {_fmt(current.value)}%，变化 {_fmt(delta)} 个百分点。",
        points=[("current", current), ("same_period_last_year", previous)],
        reports=reports,
        calculation=CalculationTrace(
            method="percentage_point_delta",
            expression=f"{_fmt(current.value)} - {_fmt(previous.value)}",
            change_value=delta,
            change_unit="percentage_point",
        ),
        generated_at=generated_at,
    )


def _gap_rule(
    rule: ChangeRuleDefinition,
    symbol: str,
    all_points: list[FundamentalMetricPoint],
    reports: dict[UUID, FinancialReport],
    generated_at: datetime,
) -> ResearchObservation | None:
    left_series = _available(all_points, rule.required_metrics[0])
    right_series = _available(all_points, rule.required_metrics[1])
    if not left_series or not right_series:
        return None
    left = left_series[-1]
    right = next(
        (item for item in reversed(right_series) if item.period_end == left.period_end),
        None,
    )
    if right is None or left.value is None or right.value is None:
        return None
    gap = left.value - right.value
    threshold = Decimal(rule.parameters["threshold_pp"])
    if abs(gap) < threshold:
        return None
    left_name = DEFINITION_BY_CODE[left.code].display_name
    right_name = DEFINITION_BY_CODE[right.code].display_name
    higher = gap > 0
    attention = (
        AttentionLevel.IMPORTANT
        if abs(gap) >= Decimal(rule.parameters.get("important_pp", "999"))
        else AttentionLevel.NOTICE
    )
    return _make_observation(
        symbol=symbol,
        rule=rule,
        observation_family=f"{left.code}.{right.code}.gap",
        observation_type="growth_mismatch",
        attention_level=attention,
        movement=Movement.UP if higher else Movement.DOWN,
        title=f"{left_name}明显{'高于' if higher else '低于'}{right_name}",
        summary=f"两项同比增速相差 {_fmt(gap)} 个百分点。",
        points=[("left_metric", left), ("right_metric", right)],
        reports=reports,
        calculation=CalculationTrace(
            method="growth_rate_gap",
            expression=f"{_fmt(left.value)} - {_fmt(right.value)}",
            change_value=gap,
            change_unit="percentage_point",
        ),
        generated_at=generated_at,
    )


def _valuation_rule(
    rule: ChangeRuleDefinition,
    symbol: str,
    all_points: list[FundamentalMetricPoint],
    reports: dict[UUID, FinancialReport],
    generated_at: datetime,
) -> ResearchObservation | None:
    code = rule.required_metrics[0]
    series = _available(all_points, code)
    if not series:
        return None
    current = series[-1]
    previous = series[-2] if len(series) > 1 else None
    if current.value is None:
        return None
    high, low = Decimal(rule.parameters["high"]), Decimal(rule.parameters["low"])
    name = "PE-TTM" if code.startswith("pe_") else "PB"
    if current.value >= high:
        entered = previous is not None and previous.value is not None and previous.value < high
        observation_type = "threshold_crossed_up" if entered else "percentile_high"
        title = f"{name}{'进入' if entered else '处于'}近三年较高分位"
        movement = Movement.CROSSED_UP if entered else Movement.NEUTRAL
    elif current.value <= low:
        entered = previous is not None and previous.value is not None and previous.value > low
        observation_type = "threshold_crossed_down" if entered else "percentile_low"
        title = f"{name}{'进入' if entered else '处于'}近三年较低分位"
        movement = Movement.CROSSED_DOWN if entered else Movement.NEUTRAL
    else:
        return None
    points: list[tuple[str, FundamentalMetricPoint]] = [("current", current)]
    if previous is not None:
        points.append(("previous_observation", previous))
    sample_count = current.detail.get("sample_count", 0)
    return _make_observation(
        symbol=symbol,
        rule=rule,
        observation_family=f"{code}.band",
        observation_type=observation_type,
        attention_level=AttentionLevel.NOTICE,
        movement=movement,
        title=title,
        summary=f"当前分位 {_fmt(current.value)}%，有效样本 {sample_count} 个观测日。",
        points=points,
        reports=reports,
        calculation=CalculationTrace(
            method="positive_sample_percentile",
            expression="count(value <= current) / positive_sample_count",
            change_value=current.value,
            change_unit="percentile",
        ),
        generated_at=generated_at,
    )


def evaluate_rules(
    *,
    symbol: str,
    issuer_type: str,
    template_version: str,
    points: list[FundamentalMetricPoint],
    reports: list[FinancialReport],
    generated_at: datetime,
) -> tuple[ResearchObservation, ...]:
    if issuer_type != "general":
        return ()
    reports_by_id = {item.id: item for item in reports}
    observations: list[ResearchObservation] = []
    for rule in RULES:
        if template_version not in rule.supported_templates:
            continue
        if rule.rule_id.startswith("growth."):
            result = _growth_rule(rule, symbol, points, reports_by_id, generated_at)
        elif rule.rule_id.startswith("profitability.") or rule.rule_id.startswith("balance."):
            result = _same_period_delta_rule(rule, symbol, points, reports_by_id, generated_at)
        elif rule.rule_id.startswith("quality."):
            result = _gap_rule(rule, symbol, points, reports_by_id, generated_at)
        else:
            result = _valuation_rule(rule, symbol, points, reports_by_id, generated_at)
        if result is not None:
            observations.append(result)
    priority = {
        AttentionLevel.IMPORTANT: 0,
        AttentionLevel.NOTICE: 1,
        AttentionLevel.INFO: 2,
    }
    return tuple(
        sorted(
            observations,
            key=lambda item: (priority[item.attention_level], item.dimension, item.title),
        )
    )
