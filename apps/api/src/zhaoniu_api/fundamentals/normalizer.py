import hashlib
import json
import math
from collections import defaultdict
from datetime import UTC, date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
from uuid import NAMESPACE_URL, uuid5

from zhaoniu_api.domain.models import IssuerType, resolve_symbol
from zhaoniu_api.fundamentals.models import (
    BalanceSheet,
    CashFlowStatement,
    FinancialReport,
    FiscalPeriod,
    IncomeStatement,
    PublishedAtPrecision,
    StatementScope,
    ValuationObservation,
)
from zhaoniu_api.market_data.errors import DataNormalizationError
from zhaoniu_api.ports.providers import RawFinancialStatement, RawValuationObservation

CN_TZ = timezone(timedelta(hours=8))
NORMALIZER_VERSION = "financial-akshare-v2"


def _clean_json(value: object) -> object:
    if value is None:
        return None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, (date, datetime, Decimal)):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _clean_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_clean_json(item) for item in value]
    return value


def _decimal(payload: dict[str, object], *names: str) -> Decimal | None:
    for name in names:
        value = payload.get(name)
        if value is None or value == "" or value is False:
            continue
        try:
            result = Decimal(str(value).replace(",", ""))
        except (InvalidOperation, ValueError) as exc:
            raise DataNormalizationError(f"invalid financial decimal: {name}") from exc
        if result.is_finite():
            return result
    return None


def _date(value: object, field_name: str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip().replace("/", "-")
    if len(text) == 8 and text.isdigit():
        text = f"{text[:4]}-{text[4:6]}-{text[6:]}"
    try:
        return date.fromisoformat(text[:10])
    except ValueError as exc:
        raise DataNormalizationError(f"invalid financial date: {field_name}") from exc


def _source_datetime(value: object | None) -> datetime | None:
    if value is None or value == "":
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise DataNormalizationError("invalid source update datetime") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=CN_TZ)
    return parsed.astimezone(UTC)


def _period(period_end: date) -> FiscalPeriod:
    mapping = {
        (3, 31): FiscalPeriod.Q1,
        (6, 30): FiscalPeriod.H1,
        (9, 30): FiscalPeriod.Q3,
        (12, 31): FiscalPeriod.FY,
    }
    try:
        return mapping[(period_end.month, period_end.day)]
    except KeyError as exc:
        raise DataNormalizationError("unsupported A-share financial reporting period") from exc


def _scope(payloads: list[dict[str, object]]) -> StatementScope:
    types = {str(payload.get("类型", "")) for payload in payloads}
    return (
        StatementScope.PARENT
        if any("母公司" in item for item in types)
        else StatementScope.CONSOLIDATED
    )


def _detect_issuer_type(balance: dict[str, object]) -> str:
    assets = _decimal(balance, "资产总计")
    liabilities = _decimal(balance, "负债合计")
    loans = _decimal(
        balance,
        "发放贷款和垫款",
        "发放贷款及垫款净额",
        "发放贷款及垫款",
        "客户贷款及垫款",
    )
    deposits = _decimal(
        balance,
        "吸收存款及同业存放",
        "吸收存款",
        "客户存款(吸收存款)",
        "客户存款",
    )
    if (
        assets
        and liabilities
        and loans
        and deposits
        and loans / assets >= Decimal("0.20")
        and deposits / liabilities >= Decimal("0.20")
    ):
        return IssuerType.BANK
    return IssuerType.GENERAL


def _income(payload: dict[str, object]) -> IncomeStatement:
    return IncomeStatement(
        total_revenue=_decimal(payload, "营业总收入"),
        revenue=_decimal(payload, "营业收入"),
        operating_cost=_decimal(payload, "营业成本"),
        selling_expenses=_decimal(payload, "销售费用"),
        administrative_expenses=_decimal(payload, "管理费用"),
        research_expenses=_decimal(payload, "研发费用"),
        finance_expenses=_decimal(payload, "财务费用"),
        operating_profit=_decimal(payload, "营业利润"),
        total_profit=_decimal(payload, "利润总额"),
        income_tax_expense=_decimal(payload, "所得税费用"),
        net_profit=_decimal(payload, "净利润"),
        parent_net_profit=_decimal(payload, "归属于母公司所有者的净利润"),
    )


def _balance(payload: dict[str, object]) -> BalanceSheet:
    return BalanceSheet(
        cash=_decimal(payload, "货币资金"),
        accounts_receivable=_decimal(payload, "应收账款"),
        inventory=_decimal(payload, "存货"),
        contract_assets=_decimal(payload, "合同资产"),
        current_assets=_decimal(payload, "流动资产合计"),
        total_assets=_decimal(payload, "资产总计"),
        short_term_borrowings=_decimal(payload, "短期借款"),
        current_portion_noncurrent_liabilities=_decimal(payload, "一年内到期的非流动负债"),
        long_term_borrowings=_decimal(payload, "长期借款"),
        bonds_payable=_decimal(payload, "应付债券"),
        lease_liabilities=_decimal(payload, "租赁负债"),
        contract_liabilities=_decimal(payload, "合同负债"),
        current_liabilities=_decimal(payload, "流动负债合计"),
        total_liabilities=_decimal(payload, "负债合计"),
        parent_equity=_decimal(payload, "归属于母公司股东权益合计", "归属于母公司所有者权益合计"),
        total_equity=_decimal(payload, "所有者权益(或股东权益)合计", "所有者权益合计"),
        goodwill=_decimal(payload, "商誉"),
    )


def _cash_flow(payload: dict[str, object]) -> CashFlowStatement:
    return CashFlowStatement(
        operating_cash_flow=_decimal(payload, "经营活动产生的现金流量净额"),
        investing_cash_flow=_decimal(payload, "投资活动产生的现金流量净额"),
        financing_cash_flow=_decimal(payload, "筹资活动产生的现金流量净额"),
        cash_paid_for_long_term_assets=_decimal(
            payload,
            "购建固定资产、无形资产和其他长期资产支付的现金",
            "购建固定资产、无形资产和其他长期资产所支付的现金",
        ),
        ending_cash=_decimal(payload, "期末现金及现金等价物余额"),
    )


class AKShareFinancialNormalizer:
    version = NORMALIZER_VERSION

    def reports(
        self,
        rows: list[RawFinancialStatement],
        *,
        observed_at: datetime | None = None,
    ) -> list[FinancialReport]:
        observation_time = observed_at or datetime.now(UTC)
        grouped: dict[str, list[RawFinancialStatement]] = defaultdict(list)
        for row in rows:
            report_date = str(row.payload.get("报告日", ""))
            if not report_date:
                raise DataNormalizationError("financial row is missing report date")
            grouped[report_date].append(row)

        reports: list[FinancialReport] = []
        for report_date, group in grouped.items():
            statement_rows = {row.statement_type: row.payload for row in group}
            if not statement_rows:
                continue
            period_end = _date(report_date, "报告日")
            payloads = list(statement_rows.values())
            symbol = resolve_symbol(group[0].requested_symbol).canonical
            published_dates = [
                _date(payload["公告日期"], "公告日期")
                for payload in payloads
                if payload.get("公告日期")
            ]
            if not published_dates:
                raise DataNormalizationError("financial report is missing announcement date")
            published_on = max(published_dates)
            published_at = datetime.combine(published_on, time.min, tzinfo=CN_TZ).astimezone(UTC)
            conservative_known_at = datetime.combine(
                published_on + timedelta(days=1), time.min, tzinfo=CN_TZ
            ).astimezone(UTC)
            source_updates = [
                item
                for item in (_source_datetime(payload.get("更新日期")) for payload in payloads)
                if item is not None
            ]
            source_updated_at = max(source_updates, default=None)
            known_at = max(conservative_known_at, source_updated_at or conservative_known_at)
            material = json.dumps(
                _clean_json(statement_rows),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            checksum = hashlib.sha256(material.encode("utf-8")).hexdigest()
            scope = _scope(payloads)
            currency = next(
                (str(payload["币种"]) for payload in payloads if payload.get("币种")), "CNY"
            )
            audit_values = {str(payload.get("是否审计", "")) for payload in payloads}
            is_audited = (
                True if any("审计" in item and "未" not in item for item in audit_values) else False
            )
            balance_payload = statement_rows.get("资产负债表", {})
            provider_revision = (
                source_updated_at.isoformat() if source_updated_at else checksum[:16]
            )
            provider_record_id = f"{symbol}:{period_end.isoformat()}:{scope}:{checksum[:16]}"
            record_id = f"{provider_record_id}:{self.version}"
            reports.append(
                FinancialReport(
                    id=uuid5(NAMESPACE_URL, record_id),
                    canonical_symbol=symbol,
                    fiscal_year=period_end.year,
                    fiscal_period=_period(period_end),
                    period_start=date(period_end.year, 1, 1),
                    period_end=period_end,
                    statement_scope=scope,
                    currency=currency,
                    provider=group[0].provider,
                    provider_record_id=provider_record_id,
                    provider_revision=provider_revision,
                    payload_checksum=checksum,
                    published_at=published_at,
                    published_at_precision=PublishedAtPrecision.DATE,
                    known_at=known_at,
                    first_observed_at=observation_time,
                    source_updated_at=source_updated_at,
                    is_audited=is_audited,
                    issuer_type=_detect_issuer_type(balance_payload),
                    income=_income(statement_rows["利润表"])
                    if "利润表" in statement_rows
                    else None,
                    balance=_balance(balance_payload) if balance_payload else None,
                    cash_flow=(
                        _cash_flow(statement_rows["现金流量表"])
                        if "现金流量表" in statement_rows
                        else None
                    ),
                    normalizer_version=self.version,
                )
            )
        return sorted(reports, key=lambda item: (item.period_end, item.known_at))

    def valuations(
        self,
        rows: list[RawValuationObservation],
        *,
        observed_at: datetime | None = None,
    ) -> list[ValuationObservation]:
        timestamp = observed_at or datetime.now(UTC)
        observations: list[ValuationObservation] = []
        for row in rows:
            value = _decimal(row.payload, "value")
            if value is None:
                continue
            if row.metric_code == "market_cap":
                value *= Decimal("100000000")
                unit = "CNY"
            else:
                unit = "multiple"
            observations.append(
                ValuationObservation(
                    canonical_symbol=resolve_symbol(row.requested_symbol).canonical,
                    trade_date=_date(row.payload.get("date"), "valuation date"),
                    metric_code=row.metric_code,
                    value=value,
                    unit=unit,
                    provider=row.provider,
                    collected_at=timestamp,
                )
            )
        identities = [
            (item.canonical_symbol, item.trade_date, item.metric_code, item.provider)
            for item in observations
        ]
        if len(identities) != len(set(identities)):
            raise DataNormalizationError("valuation response contains duplicate observations")
        return sorted(observations, key=lambda item: (item.trade_date, item.metric_code))
