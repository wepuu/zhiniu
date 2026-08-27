from __future__ import annotations

import json
from datetime import UTC, date, datetime, time, timedelta
from hashlib import sha256
from typing import Literal, cast
from uuid import UUID, uuid4

from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from zhaoniu_api.config import Settings
from zhaoniu_api.db import (
    CorporateEventRecord,
    DisclosureDocumentRecord,
    FinancialReportRevisionRecord,
    IndustryMembershipRecord,
    LLMCallRecord,
    ProviderAcceptanceItemRecord,
    ProviderAcceptanceRunRecord,
    ProviderDiagnosticRunRecord,
    StockDailyBarRecord,
    StockRecord,
    ValuationObservationRecord,
)
from zhaoniu_api.domain.models import resolve_symbol
from zhaoniu_api.provider_acceptance.models import (
    ProviderAcceptanceItem,
    ProviderAcceptanceRun,
)

PROFILE_VERSION = "phase20-beta-data-v1"
APPROVED_BETA_SCOPES = {"internal_beta", "external_beta", "production"}


def _fingerprint(value: object) -> str:
    return sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
        ).encode("utf-8")
    ).hexdigest()


def _at_midnight(value: date | None) -> datetime | None:
    return datetime.combine(value, time.min, tzinfo=UTC) if value else None


def summarize_acceptance(
    items: list[ProviderAcceptanceItem], *, policy_ok: bool
) -> tuple[Literal["passed", "failed"], bool, dict[str, int]]:
    mandatory = [item for item in items if item.requirement == "mandatory"]
    mandatory_failed = any(item.status != "passed" for item in mandatory)
    counts = {
        "mandatory": len(mandatory),
        "passed": sum(item.status == "passed" for item in items),
        "failed": sum(item.status == "failed" for item in items),
        "blocked": sum(item.status == "blocked" for item in items),
        "unsupported": sum(item.status == "unsupported" for item in items),
    }
    return ("failed" if mandatory_failed else "passed", not mandatory_failed and policy_ok, counts)


class ProviderAcceptanceService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings

    async def run(
        self, *, requested_by_user_id: UUID | None = None, as_of: datetime | None = None
    ) -> ProviderAcceptanceRun:
        started = datetime.now(UTC)
        cutoff = as_of or started
        if cutoff.tzinfo is None:
            cutoff = cutoff.replace(tzinfo=UTC)
        symbols = [
            resolve_symbol(value).canonical for value in self._settings.coverage_reference_symbols
        ]
        items: list[ProviderAcceptanceItem] = []

        policy_ok = self._settings.coverage_usage_scope in APPROVED_BETA_SCOPES
        items.append(
            self._item(
                provider="policy_registry",
                dataset="provider_usage_policy",
                scenario="beta_usage_scope",
                requirement="conditional",
                status="passed" if policy_ok else "blocked",
                reason=None if policy_ok else "provider_not_approved_for_beta_scope",
                count=1 if policy_ok else 0,
                detail={"usage_scope": self._settings.coverage_usage_scope},
            )
        )

        for symbol in symbols:
            stock = await self._session.get(StockRecord, symbol)
            stock_ok = bool(stock and stock.name and stock.exchange and stock.status == "listed")
            items.append(
                self._item(
                    provider=stock.source if stock else "unknown",
                    dataset="stock_master",
                    symbol=symbol,
                    scenario="canonical_identity",
                    requirement="mandatory",
                    status="passed" if stock_ok else "failed",
                    reason=None if stock_ok else "stock_master_missing_or_invalid",
                    count=1 if stock_ok else 0,
                    latest=stock.collected_at if stock else None,
                    detail={"issuer_type": stock.issuer_type if stock else "unknown"},
                )
            )

            bar_count, latest_bar = (
                await self._session.execute(
                    select(func.count(), func.max(StockDailyBarRecord.trade_date)).where(
                        StockDailyBarRecord.symbol == symbol,
                        StockDailyBarRecord.trade_date <= cutoff.date(),
                    )
                )
            ).one()
            market_ok = int(bar_count or 0) >= 220 and bool(
                latest_bar and latest_bar >= (cutoff - timedelta(days=7)).date()
            )
            items.append(
                self._item(
                    provider="akshare",
                    dataset="daily_bars",
                    symbol=symbol,
                    scenario="one_year_adjusted_history",
                    requirement="mandatory",
                    status="passed" if market_ok else "failed",
                    reason=None if market_ok else "daily_bar_coverage_below_threshold",
                    count=int(bar_count or 0),
                    latest=_at_midnight(latest_bar),
                    detail={"minimum_rows": 220, "freshness_days": 7},
                )
            )

            report_count, latest_report = (
                await self._session.execute(
                    select(
                        func.count(FinancialReportRevisionRecord.id),
                        func.max(FinancialReportRevisionRecord.known_at),
                    ).where(
                        FinancialReportRevisionRecord.symbol == symbol,
                        FinancialReportRevisionRecord.known_at <= cutoff,
                    )
                )
            ).one()
            financial_ok = int(report_count or 0) >= 3
            items.append(
                self._item(
                    provider="akshare",
                    dataset="financial_statements",
                    symbol=symbol,
                    scenario="retained_revision_history",
                    requirement="mandatory",
                    status="passed" if financial_ok else "failed",
                    reason=None if financial_ok else "financial_history_insufficient",
                    count=int(report_count or 0),
                    latest=latest_report,
                    detail={"minimum_revisions": 3},
                )
            )

            valuation_count, valuation_metrics, latest_valuation = (
                await self._session.execute(
                    select(
                        func.count(ValuationObservationRecord.id),
                        func.count(distinct(ValuationObservationRecord.metric_code)),
                        func.max(ValuationObservationRecord.trade_date),
                    ).where(
                        ValuationObservationRecord.symbol == symbol,
                        ValuationObservationRecord.trade_date <= cutoff.date(),
                    )
                )
            ).one()
            valuation_ok = int(valuation_metrics or 0) >= 4 and bool(
                latest_valuation and latest_valuation >= (cutoff - timedelta(days=7)).date()
            )
            items.append(
                self._item(
                    provider="akshare",
                    dataset="valuations",
                    symbol=symbol,
                    scenario="metric_and_freshness",
                    requirement="mandatory",
                    status="passed" if valuation_ok else "failed",
                    reason=None if valuation_ok else "valuation_coverage_below_threshold",
                    count=int(valuation_count or 0),
                    latest=_at_midnight(latest_valuation),
                    detail={"metric_count": int(valuation_metrics or 0), "minimum_metrics": 4},
                )
            )

            membership_count, latest_membership = (
                await self._session.execute(
                    select(
                        func.count(IndustryMembershipRecord.id),
                        func.max(IndustryMembershipRecord.known_at),
                    ).where(
                        IndustryMembershipRecord.symbol == symbol,
                        IndustryMembershipRecord.known_at <= cutoff,
                    )
                )
            ).one()
            is_bank = bool(stock and stock.issuer_type == "bank")
            industry_ok = int(membership_count or 0) > 0
            industry_status: Literal["passed", "failed", "unsupported"] = (
                "unsupported"
                if is_bank and not industry_ok
                else "passed"
                if industry_ok
                else "failed"
            )
            industry_reason = (
                "bank_template_isolated"
                if is_bank and not industry_ok
                else None
                if industry_ok
                else "industry_membership_missing"
            )
            items.append(
                self._item(
                    provider="industry_registry",
                    dataset="industry_membership",
                    symbol=symbol,
                    scenario="versioned_lineage",
                    requirement="conditional",
                    status=industry_status,
                    reason=industry_reason,
                    count=int(membership_count or 0),
                    latest=latest_membership,
                    detail={"issuer_type": stock.issuer_type if stock else "unknown"},
                )
            )

            disclosure_count, latest_disclosure = (
                await self._session.execute(
                    select(
                        func.count(DisclosureDocumentRecord.id),
                        func.max(DisclosureDocumentRecord.known_at),
                    ).where(
                        DisclosureDocumentRecord.symbol == symbol,
                        DisclosureDocumentRecord.known_at <= cutoff,
                    )
                )
            ).one()
            event_count = int(
                await self._session.scalar(
                    select(func.count(CorporateEventRecord.id)).where(
                        CorporateEventRecord.symbol == symbol,
                        CorporateEventRecord.known_at <= cutoff,
                    )
                )
                or 0
            )
            event_ok = int(disclosure_count or 0) > 0 and (event_count > 0 or is_bank)
            items.append(
                self._item(
                    provider="disclosure_pipeline",
                    dataset="corporate_events",
                    symbol=symbol,
                    scenario="retained_evidence_chain",
                    requirement="conditional",
                    status="passed" if event_ok else "failed",
                    reason=None if event_ok else "event_evidence_chain_missing",
                    count=event_count,
                    latest=latest_disclosure,
                    detail={"disclosure_count": int(disclosure_count or 0)},
                )
            )

        diagnostic = await self._session.scalar(
            select(ProviderDiagnosticRunRecord)
            .where(
                ProviderDiagnosticRunRecord.provider == "deepseek",
                ProviderDiagnosticRunRecord.target == "active",
            )
            .order_by(ProviderDiagnosticRunRecord.checked_at.desc())
            .limit(1)
        )
        successful_calls = int(
            await self._session.scalar(
                select(func.count(LLMCallRecord.id)).where(
                    LLMCallRecord.provider == "deepseek", LLMCallRecord.status == "succeeded"
                )
            )
            or 0
        )
        ai_ok = bool(diagnostic and diagnostic.status == "healthy" and successful_calls > 0)
        items.append(
            self._item(
                provider="deepseek",
                dataset="structured_ai_route",
                scenario="active_route_and_retained_success",
                requirement="optional",
                status="passed" if ai_ok else "failed",
                reason=None if ai_ok else "deepseek_acceptance_not_healthy",
                count=successful_calls,
                latest=diagnostic.checked_at if diagnostic else None,
                detail={"diagnostic_status": diagnostic.status if diagnostic else "missing"},
            )
        )

        run_status, beta_eligible, counts = summarize_acceptance(items, policy_ok=policy_ok)
        finished = datetime.now(UTC)
        result_payload = [item.model_dump(mode="json") for item in items]
        record = ProviderAcceptanceRunRecord(
            id=uuid4(),
            environment=self._settings.app_env,
            profile_version=PROFILE_VERSION,
            policy_version=self._settings.coverage_policy_version,
            usage_scope=self._settings.coverage_usage_scope,
            knowledge_cutoff=cutoff,
            status=run_status,
            mandatory_items=counts["mandatory"],
            succeeded_items=counts["passed"],
            failed_items=counts["failed"],
            blocked_items=counts["blocked"],
            unsupported_items=counts["unsupported"],
            beta_eligible=beta_eligible,
            result_fingerprint=_fingerprint(result_payload),
            requested_by_user_id=requested_by_user_id,
            started_at=started,
            finished_at=finished,
        )
        self._session.add(record)
        await self._session.flush()
        for item in items:
            self._session.add(
                ProviderAcceptanceItemRecord(
                    id=uuid4(),
                    run_id=record.id,
                    provider=item.provider,
                    dataset=item.dataset,
                    symbol=item.symbol,
                    scenario=item.scenario,
                    requirement=item.requirement,
                    status=item.status,
                    reason_code=item.reason_code,
                    observed_count=item.observed_count,
                    latest_artifact_at=item.latest_artifact_at,
                    detail_manifest=item.detail,
                    evidence_fingerprint=item.evidence_fingerprint,
                )
            )
        await self._session.commit()
        return await self.get(record.id)

    async def latest(self) -> ProviderAcceptanceRun | None:
        record = await self._session.scalar(
            select(ProviderAcceptanceRunRecord)
            .where(ProviderAcceptanceRunRecord.environment == self._settings.app_env)
            .order_by(ProviderAcceptanceRunRecord.created_at.desc())
            .limit(1)
        )
        return await self._response(record) if record else None

    async def get(self, run_id: UUID) -> ProviderAcceptanceRun:
        record = await self._session.get(ProviderAcceptanceRunRecord, run_id)
        if record is None:
            raise LookupError("provider_acceptance_run_not_found")
        return await self._response(record)

    async def list(self, limit: int = 20) -> list[ProviderAcceptanceRun]:
        records = list(
            await self._session.scalars(
                select(ProviderAcceptanceRunRecord)
                .where(ProviderAcceptanceRunRecord.environment == self._settings.app_env)
                .order_by(ProviderAcceptanceRunRecord.created_at.desc())
                .limit(limit)
            )
        )
        return [await self._response(record) for record in records]

    def _item(
        self,
        *,
        provider: str,
        dataset: str,
        scenario: str,
        requirement: Literal["mandatory", "conditional", "optional"],
        status: Literal["passed", "failed", "blocked", "unsupported"],
        reason: str | None,
        count: int,
        detail: dict[str, object],
        symbol: str | None = None,
        latest: datetime | None = None,
    ) -> ProviderAcceptanceItem:
        payload = {
            "provider": provider,
            "dataset": dataset,
            "symbol": symbol,
            "scenario": scenario,
            "status": status,
            "reason": reason,
            "count": count,
            "latest": latest,
            "detail": detail,
        }
        return ProviderAcceptanceItem(
            provider=provider,
            dataset=dataset,
            symbol=symbol,
            scenario=scenario,
            requirement=requirement,
            status=status,
            reason_code=reason,
            observed_count=count,
            latest_artifact_at=latest,
            detail=detail,
            evidence_fingerprint=_fingerprint(payload),
        )

    async def _response(self, record: ProviderAcceptanceRunRecord) -> ProviderAcceptanceRun:
        rows = list(
            await self._session.scalars(
                select(ProviderAcceptanceItemRecord)
                .where(ProviderAcceptanceItemRecord.run_id == record.id)
                .order_by(ProviderAcceptanceItemRecord.symbol, ProviderAcceptanceItemRecord.dataset)
            )
        )
        return ProviderAcceptanceRun(
            id=record.id,
            environment=record.environment,
            profile_version=record.profile_version,
            policy_version=record.policy_version,
            usage_scope=record.usage_scope,
            knowledge_cutoff=record.knowledge_cutoff,
            status=cast(Literal["passed", "failed", "blocked"], record.status),
            mandatory_items=record.mandatory_items,
            succeeded_items=record.succeeded_items,
            failed_items=record.failed_items,
            blocked_items=record.blocked_items,
            unsupported_items=record.unsupported_items,
            beta_eligible=record.beta_eligible,
            result_fingerprint=record.result_fingerprint,
            started_at=record.started_at,
            finished_at=record.finished_at,
            items=[
                ProviderAcceptanceItem(
                    provider=row.provider,
                    dataset=row.dataset,
                    symbol=row.symbol,
                    scenario=row.scenario,
                    requirement=cast(
                        Literal["mandatory", "conditional", "optional"], row.requirement
                    ),
                    status=cast(Literal["passed", "failed", "blocked", "unsupported"], row.status),
                    reason_code=row.reason_code,
                    observed_count=row.observed_count,
                    latest_artifact_at=row.latest_artifact_at,
                    detail=row.detail_manifest,
                    evidence_fingerprint=row.evidence_fingerprint,
                )
                for row in rows
            ],
        )
