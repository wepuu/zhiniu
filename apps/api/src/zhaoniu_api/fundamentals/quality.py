from dataclasses import replace
from decimal import Decimal

from zhaoniu_api.fundamentals.models import FinancialReport
from zhaoniu_api.market_data.errors import DataQualityError


def validate_financial_report(report: FinancialReport) -> FinancialReport:
    warnings: list[str] = []
    if report.period_start > report.period_end:
        raise DataQualityError("financial period start is after period end")
    if report.currency != "CNY":
        warnings.append("non_cny_currency")
    balance = report.balance
    if balance is not None:
        if balance.total_assets is not None and balance.total_assets <= 0:
            raise DataQualityError("total assets must be positive")
        if balance.total_liabilities is not None and balance.total_liabilities < 0:
            raise DataQualityError("total liabilities must be non-negative")
        if (
            balance.total_assets is not None
            and balance.total_liabilities is not None
            and balance.total_equity is not None
        ):
            difference = abs(
                balance.total_assets - balance.total_liabilities - balance.total_equity
            )
            tolerance = max(Decimal("1"), abs(balance.total_assets) * Decimal("0.001"))
            if difference > tolerance:
                warnings.append("accounting_identity_outside_tolerance")
    return replace(report, quality_warnings=tuple(sorted(set(warnings))))


def validate_financial_batch(
    reports: list[FinancialReport], expected_symbol: str
) -> list[FinancialReport]:
    identities = [
        (
            report.canonical_symbol,
            report.period_end,
            report.statement_scope,
            report.payload_checksum,
        )
        for report in reports
    ]
    if len(identities) != len(set(identities)):
        raise DataQualityError("financial batch contains duplicate report revisions")
    validated: list[FinancialReport] = []
    for report in reports:
        if report.canonical_symbol != expected_symbol:
            raise DataQualityError("financial batch contains a mismatched symbol")
        validated.append(validate_financial_report(report))
    return sorted(validated, key=lambda item: (item.period_end, item.known_at))
