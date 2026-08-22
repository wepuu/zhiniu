import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal, getcontext

from zhaoniu_api.domain.models import IssuerType
from zhaoniu_api.fundamentals.models import (
    FinancialReport,
    FiscalPeriod,
    FundamentalMetric,
    MetricBasis,
    MetricStatus,
    ValuationObservation,
)

METRIC_VERSION = "fundamentals-v1"
PERCENT = Decimal("100")


@dataclass(frozen=True, slots=True)
class MetricDefinition:
    code: str
    display_name: str
    dimension: str
    unit: str
    description: str


METRIC_DEFINITIONS = (
    MetricDefinition(
        "revenue_yoy", "营业收入同比", "growth", "percent", "同口径累计营业收入同比变化"
    ),
    MetricDefinition(
        "parent_net_profit_yoy",
        "归母净利润同比",
        "growth",
        "percent",
        "同口径累计归母净利润同比变化",
    ),
    MetricDefinition(
        "revenue_single_quarter_yoy",
        "单季度收入同比",
        "growth",
        "percent",
        "累计流量表推导的单季度同比",
    ),
    MetricDefinition(
        "parent_net_profit_single_quarter_yoy",
        "单季度归母净利润同比",
        "growth",
        "percent",
        "累计流量表推导的单季度同比",
    ),
    MetricDefinition(
        "revenue_cagr_3y",
        "营业收入三年复合增速",
        "growth",
        "percent",
        "最近完整年度与三年前完整年度之间的复合增速",
    ),
    MetricDefinition(
        "parent_net_profit_cagr_3y",
        "归母净利润三年复合增速",
        "growth",
        "percent",
        "最近完整年度与三年前完整年度之间的复合增速",
    ),
    MetricDefinition(
        "gross_margin", "毛利率", "profitability", "percent", "营业收入减营业成本后占营业收入比例"
    ),
    MetricDefinition(
        "parent_net_margin", "归母净利率", "profitability", "percent", "归母净利润占营业收入比例"
    ),
    MetricDefinition(
        "roe_avg_equity_fy",
        "年度平均权益 ROE",
        "profitability",
        "percent",
        "完整年度归母净利润除以平均归母权益",
    ),
    MetricDefinition(
        "roa_avg_assets_fy",
        "年度平均资产 ROA",
        "profitability",
        "percent",
        "完整年度净利润除以平均总资产",
    ),
    MetricDefinition(
        "operating_cash_flow", "经营现金流", "quality", "CNY", "经营活动产生的现金流量净额"
    ),
    MetricDefinition(
        "operating_cash_flow_yoy",
        "经营现金流同比",
        "quality",
        "percent",
        "同口径经营活动产生的现金流量净额同比变化",
    ),
    MetricDefinition(
        "ocf_to_parent_net_profit", "现金利润比", "quality", "ratio", "经营现金流除以归母净利润"
    ),
    MetricDefinition(
        "accounts_receivable_yoy", "应收账款同比", "quality", "percent", "应收账款相对上年同期变化"
    ),
    MetricDefinition("inventory_yoy", "存货同比", "quality", "percent", "存货相对上年同期变化"),
    MetricDefinition(
        "free_cash_flow", "自由现金流", "quality", "CNY", "经营现金流减购建长期资产支付现金"
    ),
    MetricDefinition("debt_to_assets", "资产负债率", "balance", "percent", "总负债占总资产比例"),
    MetricDefinition("cash", "货币资金", "balance", "CNY", "资产负债表披露的货币资金"),
    MetricDefinition(
        "interest_bearing_debt",
        "有息负债",
        "balance",
        "CNY",
        "短期借款、一年内到期非流动负债、长期借款、应付债券和租赁负债之和",
    ),
    MetricDefinition("net_debt", "净负债", "balance", "CNY", "有息负债减货币资金"),
    MetricDefinition("current_ratio", "流动比率", "balance", "ratio", "流动资产除以流动负债"),
    MetricDefinition(
        "goodwill_to_assets", "商誉占总资产", "balance", "percent", "商誉占总资产比例"
    ),
    MetricDefinition(
        "pe_ttm", "市盈率 TTM", "valuation", "multiple", "Provider 披露的滚动市盈率观测值"
    ),
    MetricDefinition("pb", "市净率", "valuation", "multiple", "Provider 披露的市净率观测值"),
    MetricDefinition("pcf", "市现率", "valuation", "multiple", "Provider 披露的市现率观测值"),
    MetricDefinition(
        "market_cap", "总市值", "valuation", "CNY", "Provider 披露并统一为人民币元的总市值"
    ),
    MetricDefinition(
        "pe_ttm_percentile_3y",
        "市盈率三年分位",
        "valuation",
        "percent",
        "当前正市盈率在三年有效样本中的分位",
    ),
    MetricDefinition(
        "pb_percentile_3y",
        "市净率三年分位",
        "valuation",
        "percent",
        "当前正市净率在三年有效样本中的分位",
    ),
)

DEFINITION_BY_CODE = {definition.code: definition for definition in METRIC_DEFINITIONS}
GENERAL_CODES = tuple(
    definition.code for definition in METRIC_DEFINITIONS if definition.dimension != "valuation"
)


def make_data_version(reports: list[FinancialReport]) -> str:
    material = "|".join(sorted(f"{report.id}:{report.payload_checksum}" for report in reports))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _quantize(value: Decimal, unit: str) -> Decimal:
    places = Decimal("0.0001") if unit in {"percent", "ratio", "multiple"} else Decimal("0.01")
    return value.quantize(places)


def _result(
    code: str,
    report: FinancialReport | None,
    value: Decimal | None,
    *,
    status: MetricStatus | None = None,
    basis: MetricBasis = MetricBasis.YTD,
    inputs: tuple[FinancialReport, ...] = (),
    detail: str | None = None,
) -> FundamentalMetric:
    definition = DEFINITION_BY_CODE[code]
    final_status = status or (
        MetricStatus.AVAILABLE if value is not None else MetricStatus.MISSING_INPUT
    )
    return FundamentalMetric(
        code=code,
        value=_quantize(value, definition.unit) if value is not None else None,
        unit=definition.unit,
        status=final_status,
        period_end=report.period_end if report else None,
        basis=basis,
        input_report_ids=tuple(item.id for item in inputs),
        detail=detail,
    )


def _divide(numerator: Decimal | None, denominator: Decimal | None) -> Decimal | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


def _growth(current: Decimal | None, previous: Decimal | None) -> Decimal | None:
    ratio = (
        _divide(current - previous, abs(previous))
        if current is not None and previous is not None
        else None
    )
    return ratio * PERCENT if ratio is not None else None


def _matching_prior(
    report: FinancialReport, reports: list[FinancialReport]
) -> FinancialReport | None:
    return next(
        (
            item
            for item in reports
            if item.period_end.year == report.period_end.year - 1
            and item.fiscal_period == report.fiscal_period
            and item.statement_scope == report.statement_scope
        ),
        None,
    )


def _standalone_value(
    report: FinancialReport,
    reports: list[FinancialReport],
    getter: Callable[[FinancialReport], Decimal | None],
) -> tuple[Decimal | None, tuple[FinancialReport, ...]]:
    current = getter(report)
    if current is None:
        return None, (report,)
    previous_period = {
        FiscalPeriod.Q1: None,
        FiscalPeriod.H1: FiscalPeriod.Q1,
        FiscalPeriod.Q3: FiscalPeriod.H1,
        FiscalPeriod.FY: FiscalPeriod.Q3,
    }[report.fiscal_period]
    if previous_period is None:
        return current, (report,)
    previous = next(
        (
            item
            for item in reports
            if item.fiscal_year == report.fiscal_year
            and item.fiscal_period == previous_period
            and item.statement_scope == report.statement_scope
        ),
        None,
    )
    previous_value = getter(previous) if previous is not None else None
    if previous is None or previous_value is None:
        return None, (report,)
    return current - previous_value, (report, previous)


def _latest_fy(reports: list[FinancialReport]) -> FinancialReport | None:
    annual = [report for report in reports if report.fiscal_period == FiscalPeriod.FY]
    return max(annual, key=lambda item: item.period_end, default=None)


def compute_fundamental_metrics(reports: list[FinancialReport]) -> tuple[FundamentalMetric, ...]:
    if not reports:
        return tuple(
            _result(code, None, None, status=MetricStatus.MISSING_INPUT) for code in GENERAL_CODES
        )
    latest = max(reports, key=lambda item: item.period_end)
    if latest.issuer_type != IssuerType.GENERAL:
        return tuple(
            _result(
                code,
                latest,
                None,
                status=MetricStatus.NOT_APPLICABLE,
                detail="financial_issuer_template_not_supported",
            )
            for code in GENERAL_CODES
        )
    prior = _matching_prior(latest, reports)
    income = latest.income
    prior_income = prior.income if prior else None
    balance = latest.balance
    prior_balance = prior.balance if prior else None
    cash_flow = latest.cash_flow
    metrics: list[FundamentalMetric] = []

    revenue = income.revenue if income else None
    prior_revenue = prior_income.revenue if prior_income else None
    parent_profit = income.parent_net_profit if income else None
    prior_parent_profit = prior_income.parent_net_profit if prior_income else None
    prior_inputs = (latest, prior) if prior else (latest,)
    metrics.append(
        _result("revenue_yoy", latest, _growth(revenue, prior_revenue), inputs=prior_inputs)
    )
    metrics.append(
        _result(
            "parent_net_profit_yoy",
            latest,
            _growth(parent_profit, prior_parent_profit),
            inputs=prior_inputs,
        )
    )

    current_sq_revenue, current_sq_revenue_inputs = _standalone_value(
        latest, reports, lambda item: item.income.revenue if item.income else None
    )
    current_sq_profit, current_sq_profit_inputs = _standalone_value(
        latest, reports, lambda item: item.income.parent_net_profit if item.income else None
    )
    if prior:
        prior_sq_revenue, prior_sq_revenue_inputs = _standalone_value(
            prior, reports, lambda item: item.income.revenue if item.income else None
        )
        prior_sq_profit, prior_sq_profit_inputs = _standalone_value(
            prior, reports, lambda item: item.income.parent_net_profit if item.income else None
        )
    else:
        prior_sq_revenue, prior_sq_profit = None, None
        prior_sq_revenue_inputs, prior_sq_profit_inputs = (), ()
    metrics.append(
        _result(
            "revenue_single_quarter_yoy",
            latest,
            _growth(current_sq_revenue, prior_sq_revenue),
            basis=MetricBasis.STANDALONE,
            inputs=current_sq_revenue_inputs + prior_sq_revenue_inputs,
            detail="derived_from_cumulative_flows",
        )
    )
    metrics.append(
        _result(
            "parent_net_profit_single_quarter_yoy",
            latest,
            _growth(current_sq_profit, prior_sq_profit),
            basis=MetricBasis.STANDALONE,
            inputs=current_sq_profit_inputs + prior_sq_profit_inputs,
            detail="derived_from_cumulative_flows",
        )
    )

    annual = _latest_fy(reports)
    cagr_metrics: tuple[tuple[str, Callable[[FinancialReport], Decimal | None]], ...] = (
        ("revenue_cagr_3y", lambda item: item.income.revenue if item.income else None),
        (
            "parent_net_profit_cagr_3y",
            lambda item: item.income.parent_net_profit if item.income else None,
        ),
    )
    for code, getter in cagr_metrics:
        earlier = next(
            (
                item
                for item in reports
                if annual
                and item.fiscal_period == FiscalPeriod.FY
                and item.fiscal_year == annual.fiscal_year - 3
            ),
            None,
        )
        current_value = getter(annual) if annual else None
        earlier_value = getter(earlier) if earlier else None
        if current_value is None or earlier_value is None:
            metrics.append(
                _result(
                    code,
                    annual,
                    None,
                    status=MetricStatus.INSUFFICIENT_HISTORY,
                    basis=MetricBasis.FY,
                )
            )
        elif current_value <= 0 or earlier_value <= 0:
            metrics.append(
                _result(code, annual, None, status=MetricStatus.INVALID_INPUT, basis=MetricBasis.FY)
            )
        else:
            cagr = (
                getcontext().power(current_value / earlier_value, Decimal(1) / Decimal(3)) - 1
            ) * PERCENT
            cagr_inputs = tuple(item for item in (annual, earlier) if item is not None)
            metrics.append(_result(code, annual, cagr, basis=MetricBasis.FY, inputs=cagr_inputs))

    gross_profit = (
        revenue - income.operating_cost
        if revenue is not None and income and income.operating_cost is not None
        else None
    )
    metrics.append(
        _result(
            "gross_margin",
            latest,
            (_divide(gross_profit, revenue) or Decimal(0)) * PERCENT
            if gross_profit is not None and revenue
            else None,
            inputs=(latest,),
        )
    )
    metrics.append(
        _result(
            "parent_net_margin",
            latest,
            (_divide(parent_profit, revenue) or Decimal(0)) * PERCENT
            if parent_profit is not None and revenue
            else None,
            inputs=(latest,),
        )
    )

    previous_fy = next(
        (
            item
            for item in reports
            if annual
            and item.fiscal_period == FiscalPeriod.FY
            and item.fiscal_year == annual.fiscal_year - 1
        ),
        None,
    )
    annual_profit = annual.income.parent_net_profit if annual and annual.income else None
    annual_net_profit = annual.income.net_profit if annual and annual.income else None
    average_equity = (
        (annual.balance.parent_equity + previous_fy.balance.parent_equity) / 2
        if annual
        and previous_fy
        and annual.balance
        and previous_fy.balance
        and annual.balance.parent_equity is not None
        and previous_fy.balance.parent_equity is not None
        else None
    )
    average_assets = (
        (annual.balance.total_assets + previous_fy.balance.total_assets) / 2
        if annual
        and previous_fy
        and annual.balance
        and previous_fy.balance
        and annual.balance.total_assets is not None
        and previous_fy.balance.total_assets is not None
        else None
    )
    annual_inputs = (
        (annual, previous_fy)
        if annual and previous_fy
        else tuple(item for item in (annual,) if item)
    )
    metrics.append(
        _result(
            "roe_avg_equity_fy",
            annual,
            (_divide(annual_profit, average_equity) or Decimal(0)) * PERCENT
            if annual_profit is not None and average_equity
            else None,
            basis=MetricBasis.FY,
            inputs=annual_inputs,
        )
    )
    metrics.append(
        _result(
            "roa_avg_assets_fy",
            annual,
            (_divide(annual_net_profit, average_assets) or Decimal(0)) * PERCENT
            if annual_net_profit is not None and average_assets
            else None,
            basis=MetricBasis.FY,
            inputs=annual_inputs,
        )
    )

    ocf = cash_flow.operating_cash_flow if cash_flow else None
    prior_ocf = (
        prior.cash_flow.operating_cash_flow if prior and prior.cash_flow is not None else None
    )
    capex = cash_flow.cash_paid_for_long_term_assets if cash_flow else None
    metrics.append(_result("operating_cash_flow", latest, ocf, inputs=(latest,)))
    metrics.append(
        _result(
            "operating_cash_flow_yoy",
            latest,
            _growth(ocf, prior_ocf) if prior_ocf is not None and prior_ocf > 0 else None,
            status=(
                MetricStatus.INVALID_INPUT if prior_ocf is not None and prior_ocf <= 0 else None
            ),
            inputs=prior_inputs,
        )
    )
    metrics.append(
        _result("ocf_to_parent_net_profit", latest, _divide(ocf, parent_profit), inputs=(latest,))
    )
    metrics.append(
        _result(
            "accounts_receivable_yoy",
            latest,
            _growth(
                balance.accounts_receivable if balance else None,
                prior_balance.accounts_receivable if prior_balance else None,
            ),
            basis=MetricBasis.POINT_IN_TIME,
            inputs=prior_inputs,
        )
    )
    metrics.append(
        _result(
            "inventory_yoy",
            latest,
            _growth(
                balance.inventory if balance else None,
                prior_balance.inventory if prior_balance else None,
            ),
            basis=MetricBasis.POINT_IN_TIME,
            inputs=prior_inputs,
        )
    )
    metrics.append(
        _result(
            "free_cash_flow",
            latest,
            ocf - capex if ocf is not None and capex is not None else None,
            inputs=(latest,),
        )
    )

    assets = balance.total_assets if balance else None
    liabilities = balance.total_liabilities if balance else None
    cash = balance.cash if balance else None
    debt_parts = (
        (
            balance.short_term_borrowings,
            balance.current_portion_noncurrent_liabilities,
            balance.long_term_borrowings,
            balance.bonds_payable,
            balance.lease_liabilities,
        )
        if balance
        else ()
    )
    debt = (
        sum((item for item in debt_parts if item is not None), Decimal(0))
        if any(item is not None for item in debt_parts)
        else None
    )
    metrics.append(
        _result(
            "debt_to_assets",
            latest,
            (_divide(liabilities, assets) or Decimal(0)) * PERCENT
            if liabilities is not None and assets
            else None,
            basis=MetricBasis.POINT_IN_TIME,
            inputs=(latest,),
        )
    )
    metrics.append(_result("cash", latest, cash, basis=MetricBasis.POINT_IN_TIME, inputs=(latest,)))
    metrics.append(
        _result(
            "interest_bearing_debt", latest, debt, basis=MetricBasis.POINT_IN_TIME, inputs=(latest,)
        )
    )
    metrics.append(
        _result(
            "net_debt",
            latest,
            debt - cash if debt is not None and cash is not None else None,
            basis=MetricBasis.POINT_IN_TIME,
            inputs=(latest,),
        )
    )
    metrics.append(
        _result(
            "current_ratio",
            latest,
            _divide(balance.current_assets, balance.current_liabilities) if balance else None,
            basis=MetricBasis.POINT_IN_TIME,
            inputs=(latest,),
        )
    )
    metrics.append(
        _result(
            "goodwill_to_assets",
            latest,
            (_divide(balance.goodwill, assets) or Decimal(0)) * PERCENT
            if balance and balance.goodwill is not None and assets
            else None,
            basis=MetricBasis.POINT_IN_TIME,
            inputs=(latest,),
        )
    )
    return tuple(metrics)


def compute_valuation_metrics(
    observations: list[ValuationObservation],
) -> tuple[FundamentalMetric, ...]:
    results: list[FundamentalMetric] = []
    by_code: dict[str, list[ValuationObservation]] = {}
    for observation in observations:
        by_code.setdefault(observation.metric_code, []).append(observation)
    for code in ("pe_ttm", "pb", "pcf", "market_cap"):
        values = sorted(by_code.get(code, []), key=lambda item: item.trade_date)
        latest = values[-1] if values else None
        results.append(
            FundamentalMetric(
                code=code,
                value=_quantize(latest.value, DEFINITION_BY_CODE[code].unit) if latest else None,
                unit=DEFINITION_BY_CODE[code].unit,
                status=MetricStatus.AVAILABLE if latest else MetricStatus.MISSING_INPUT,
                period_end=latest.trade_date if latest else None,
                basis=MetricBasis.POINT_IN_TIME,
                detail=f"provider:{latest.provider}" if latest else None,
            )
        )
    for source_code, percentile_code in (
        ("pe_ttm", "pe_ttm_percentile_3y"),
        ("pb", "pb_percentile_3y"),
    ):
        values = sorted(by_code.get(source_code, []), key=lambda item: item.trade_date)
        latest = values[-1] if values else None
        if latest is None:
            results.append(
                _result(
                    percentile_code,
                    None,
                    None,
                    status=MetricStatus.MISSING_INPUT,
                    basis=MetricBasis.POINT_IN_TIME,
                )
            )
            continue
        cutoff = latest.trade_date - timedelta(days=365 * 3)
        valid = [item.value for item in values if item.trade_date >= cutoff and item.value > 0]
        if len(valid) < 250:
            results.append(
                FundamentalMetric(
                    code=percentile_code,
                    value=None,
                    unit="percent",
                    status=MetricStatus.INSUFFICIENT_HISTORY,
                    period_end=latest.trade_date,
                    basis=MetricBasis.POINT_IN_TIME,
                    detail=f"valid_samples:{len(valid)}",
                )
            )
            continue
        percentile = (
            Decimal(sum(value <= latest.value for value in valid)) / Decimal(len(valid)) * PERCENT
        )
        results.append(
            FundamentalMetric(
                code=percentile_code,
                value=_quantize(percentile, "percent"),
                unit="percent",
                status=MetricStatus.AVAILABLE,
                period_end=latest.trade_date,
                basis=MetricBasis.POINT_IN_TIME,
                detail=f"valid_samples:{len(valid)}",
            )
        )
    return tuple(results)
