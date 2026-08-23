import argparse
import asyncio
import json
from dataclasses import asdict, is_dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from uuid import UUID

from sqlalchemy import select

from zhaoniu_api.ai_research.models import AIResearchBuildResult
from zhaoniu_api.company_timeline.service import CompanyTimelineQueryService
from zhaoniu_api.composition import (
    build_access_control_service,
    build_ai_research_service,
    build_automation_service,
    build_corporate_event_service,
    build_coverage_service,
    build_fundamental_service,
    build_market_data_service,
    build_peer_research_service,
    build_research_feed_service,
    build_research_service,
    build_screening_service,
)
from zhaoniu_api.config import get_settings
from zhaoniu_api.corporate_events.models import EventBuildResult
from zhaoniu_api.database import engine, session_factory
from zhaoniu_api.db import User
from zhaoniu_api.domain.models import resolve_symbol
from zhaoniu_api.fundamentals.models import FundamentalSnapshot
from zhaoniu_api.market_data.akshare_provider import AKShareProvider
from zhaoniu_api.market_data.errors import safe_market_error_code
from zhaoniu_api.market_data.service import SyncResult
from zhaoniu_api.operations import evaluate_beta_readiness
from zhaoniu_api.operations_console.service import OperatorService
from zhaoniu_api.peer_research.models import PeerBuildResult
from zhaoniu_api.peer_research.service import IndustrySyncResult
from zhaoniu_api.provider_configuration.crypto import generate_key
from zhaoniu_api.provider_configuration.service import ProviderConfigurationService
from zhaoniu_api.research.models import ResearchBuildResult
from zhaoniu_api.screening.models import ScreeningBuildResult, ScreenQuery


def _date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected YYYY-MM-DD") from exc


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="zhaoniu-market-data")
    subcommands = parser.add_subparsers(dest="command", required=True)
    master = subcommands.add_parser("sync-stock-master")
    master.add_argument("--force", action="store_true")
    daily = subcommands.add_parser("sync-daily-bars")
    daily.add_argument("symbol")
    daily.add_argument("--start", type=_date)
    daily.add_argument("--end", type=_date)
    daily.add_argument("--force", action="store_true")
    diagnosis = subcommands.add_parser("diagnose-market-provider")
    diagnosis.add_argument("symbol")
    financials = subcommands.add_parser("sync-financial-statements")
    financials.add_argument("symbol")
    financials.add_argument("--start-year", type=int, default=date.today().year - 6)
    financials.add_argument("--force", action="store_true")
    valuations = subcommands.add_parser("sync-valuations")
    valuations.add_argument("symbol")
    valuations.add_argument("--start", type=_date)
    valuations.add_argument("--end", type=_date)
    valuations.add_argument("--force", action="store_true")
    compute = subcommands.add_parser("compute-fundamentals")
    compute.add_argument("symbol")
    compute.add_argument("--as-of", type=datetime.fromisoformat)
    research = subcommands.add_parser("build-research-snapshot")
    research.add_argument("symbol")
    research.add_argument("--as-of", type=datetime.fromisoformat)
    ai_research = subcommands.add_parser("generate-ai-stock-health")
    ai_research.add_argument("symbol")
    ai_research.add_argument("--retry-failed", action="store_true")
    subcommands.add_parser("sync-industries")
    peer_benchmark = subcommands.add_parser("build-peer-benchmark")
    peer_benchmark.add_argument("symbol")
    peer_benchmark.add_argument("--as-of", type=datetime.fromisoformat)
    peer_research = subcommands.add_parser("build-peer-research")
    peer_research.add_argument("symbol")
    peer_research.add_argument("--as-of", type=datetime.fromisoformat)
    disclosures = subcommands.add_parser("sync-disclosures")
    disclosures.add_argument("symbol")
    disclosures.add_argument("--start", type=_date)
    disclosures.add_argument("--end", type=_date)
    corporate_events = subcommands.add_parser("build-corporate-events")
    corporate_events.add_argument("symbol")
    event_radar = subcommands.add_parser("build-event-radar")
    event_radar.add_argument("symbol")
    event_radar.add_argument("--as-of", type=datetime.fromisoformat)
    event_research = subcommands.add_parser("build-event-research")
    event_research.add_argument("symbol")
    signal_projection = subcommands.add_parser("project-research-signals")
    signal_projection.add_argument("symbol")
    timeline = subcommands.add_parser("inspect-company-timeline")
    timeline.add_argument("symbol")
    dispatch_alert = subcommands.add_parser("dispatch-research-alert")
    dispatch_alert.add_argument("signal_id")
    screening_snapshot = subcommands.add_parser("build-screening-snapshot")
    screening_snapshot.add_argument("--as-of", type=datetime.fromisoformat)
    validate_screen = subcommands.add_parser("validate-screen")
    validate_screen.add_argument("--query-file", type=Path, required=True)
    execute_screen = subcommands.add_parser("execute-screen")
    execute_screen.add_argument("--query-file", type=Path, required=True)
    execute_screen.add_argument("--user-email", required=True)
    invites = subcommands.add_parser("generate-registration-invites")
    invites.add_argument("--count", type=int, default=1)
    invites.add_argument("--expires-in-days", type=int, default=14)
    invites.add_argument("--name")
    access_code = subcommands.add_parser("issue-access-code")
    access_code.add_argument("--user-email", required=True)
    access_code.add_argument("--term", choices=("month", "year"), required=True)
    access_code.add_argument("--expires-in-days", type=int, default=7)
    inspect_access = subcommands.add_parser("inspect-user-access")
    inspect_access.add_argument("--user-email", required=True)
    subcommands.add_parser("check-beta-readiness")
    subcommands.add_parser("beta-status")
    universe = subcommands.add_parser("build-beta-research-universe")
    universe.add_argument("--symbol", action="append", dest="symbols")
    coverage = subcommands.add_parser("build-research-coverage-snapshot")
    coverage.add_argument("--universe-id", type=UUID)
    stock_coverage = subcommands.add_parser("show-stock-coverage")
    stock_coverage.add_argument("symbol")
    backfill_plan = subcommands.add_parser("plan-coverage-backfill")
    backfill_plan.add_argument("--coverage-snapshot-id", type=UUID)
    backfill_run = subcommands.add_parser("run-coverage-backfill")
    backfill_run.add_argument("run_id", type=UUID)
    backfill_status = subcommands.add_parser("coverage-backfill-status")
    backfill_status.add_argument("run_id", type=UUID)
    backfill_recover = subcommands.add_parser("recover-coverage-backfill")
    backfill_recover.add_argument("run_id", type=UUID)
    learning = subcommands.add_parser("generate-beta-learning-report")
    learning.add_argument("--days", type=int, choices=(7, 30), default=7)
    feedback = subcommands.add_parser("list-beta-feedback")
    feedback.add_argument("--limit", type=int, default=100)
    feedback_status = subcommands.add_parser("update-beta-feedback-status")
    feedback_status.add_argument("feedback_id", type=UUID)
    feedback_status.add_argument("status", choices=("triaged", "resolved"))
    grant_operator = subcommands.add_parser("grant-operator")
    grant_operator.add_argument("--email", required=True)
    grant_operator.add_argument(
        "--role", choices=("viewer", "support", "operations", "security_admin"), required=True
    )
    revoke_operator = subcommands.add_parser("revoke-operator")
    revoke_operator.add_argument("--email", required=True)
    subcommands.add_parser("list-operators")
    subcommands.add_parser("check-production-readiness")
    subcommands.add_parser("automation-tick")
    automation_run = subcommands.add_parser("automation-run")
    automation_run.add_argument("policy_key", nargs="?", default="priority_daily_refresh")
    automation_resume = subcommands.add_parser("automation-resume")
    automation_resume.add_argument("run_id", type=UUID)
    automation_refresh = subcommands.add_parser("automation-refresh-stock")
    automation_refresh.add_argument("symbol")
    subcommands.add_parser("generate-provider-encryption-key")
    reencrypt = subcommands.add_parser("reencrypt-provider-credentials")
    reencrypt.add_argument("--to-key-id", required=True)
    reencrypt.add_argument("--operator-email", required=True)
    return parser


async def _run(args: argparse.Namespace) -> None:
    try:
        async with session_factory() as session:
            result: (
                SyncResult
                | FundamentalSnapshot
                | ResearchBuildResult
                | AIResearchBuildResult
                | IndustrySyncResult
                | PeerBuildResult
                | EventBuildResult
                | ScreeningBuildResult
                | object
            )
            if args.command == "sync-stock-master":
                result = await build_market_data_service(session).sync_stock_master(
                    force=args.force
                )
            elif args.command == "sync-daily-bars":
                result = await build_market_data_service(session).sync_daily_bars(
                    args.symbol, start=args.start, end=args.end, force=args.force
                )
            elif args.command == "diagnose-market-provider":
                settings = get_settings()
                resolved = resolve_symbol(args.symbol)
                provider = AKShareProvider(
                    max_attempts=settings.akshare_max_attempts,
                    retry_backoff_seconds=settings.akshare_retry_backoff_seconds,
                )
                diagnosis_end = date.today()
                try:
                    diagnosis_rows = await provider.get_daily_bars(
                        resolved.ticker, diagnosis_end - timedelta(days=14), diagnosis_end
                    )
                    result = {
                        "status": "healthy",
                        "provider": provider.name,
                        "symbol": resolved.canonical,
                        "received_count": len(diagnosis_rows),
                    }
                except Exception as exc:
                    result = {
                        "status": "unavailable",
                        "provider": provider.name,
                        "symbol": resolved.canonical,
                        "reason_code": safe_market_error_code(exc),
                    }
            elif args.command == "sync-financial-statements":
                result = await build_fundamental_service(session).sync_financial_statements(
                    args.symbol, start_year=args.start_year, force=args.force
                )
            elif args.command == "sync-valuations":
                result = await build_fundamental_service(session).sync_valuations(
                    args.symbol, start=args.start, end=args.end, force=args.force
                )
            elif args.command == "build-research-snapshot":
                result = await build_research_service(session).build_snapshot(
                    args.symbol, as_of=args.as_of
                )
            elif args.command == "generate-ai-stock-health":
                result = await build_ai_research_service(session).generate_stock_health(
                    args.symbol, retry_failed=args.retry_failed
                )
            elif args.command == "sync-industries":
                result = await build_peer_research_service(session).sync_industries()
            elif args.command == "build-peer-benchmark":
                result = await build_peer_research_service(session).build_peer_benchmark(
                    args.symbol, as_of=args.as_of
                )
            elif args.command == "build-peer-research":
                result = await build_peer_research_service(session).build_peer_research(
                    args.symbol, as_of=args.as_of
                )
            elif args.command == "sync-disclosures":
                result = await build_corporate_event_service(session).sync_disclosures(
                    args.symbol, start=args.start, end=args.end
                )
            elif args.command == "build-corporate-events":
                result = await build_corporate_event_service(session).build_corporate_events(
                    args.symbol
                )
            elif args.command == "build-event-radar":
                result = await build_corporate_event_service(session).build_event_radar(
                    args.symbol, as_of=args.as_of
                )
            elif args.command == "build-event-research":
                result = await build_corporate_event_service(session).build_event_research(
                    args.symbol
                )
            elif args.command == "project-research-signals":
                result = await build_research_feed_service(session).project_symbol(
                    args.symbol, projection_mode="historical_backfill"
                )
            elif args.command == "inspect-company-timeline":
                result = await CompanyTimelineQueryService(session).get(
                    args.symbol,
                    source_kind=None,
                    minimum_attention=None,
                    limit=20,
                    cursor=None,
                )
            elif args.command == "dispatch-research-alert":
                from uuid import UUID

                result = await build_research_feed_service(session).dispatch(UUID(args.signal_id))
            elif args.command == "build-screening-snapshot":
                result = await build_screening_service(session).build_snapshot(args.as_of)
            elif args.command == "validate-screen":
                query = ScreenQuery.model_validate_json(args.query_file.read_text(encoding="utf-8"))
                result = build_screening_service(session).validate(query)
            elif args.command == "execute-screen":
                query = ScreenQuery.model_validate_json(args.query_file.read_text(encoding="utf-8"))
                user_id = await session.scalar(select(User.id).where(User.email == args.user_email))
                if user_id is None:
                    raise ValueError("user_not_found")
                screening = build_screening_service(session)
                claimed = await screening.create_execution(user_id, query)
                result = await screening.execute(claimed.id)
            elif args.command == "generate-registration-invites":
                access = build_access_control_service(session)
                result = await access.generate_registration_invites(
                    count=args.count,
                    expires_in_days=args.expires_in_days,
                    operator=get_settings().access_operator_id,
                    name=args.name,
                )
            elif args.command == "issue-access-code":
                access = build_access_control_service(session)
                result = await access.issue_access_code(
                    user_email=args.user_email,
                    term_kind=args.term,
                    expires_in_days=args.expires_in_days,
                    operator=get_settings().access_operator_id,
                )
            elif args.command == "inspect-user-access":
                user_id = await session.scalar(
                    select(User.id).where(User.email == args.user_email.strip().lower())
                )
                if user_id is None:
                    raise ValueError("user_not_found")
                result = await build_access_control_service(session).access_envelope(user_id)
            elif args.command in {"check-beta-readiness", "beta-status"}:
                result = await evaluate_beta_readiness(session, get_settings())
            elif args.command == "build-beta-research-universe":
                result = await build_coverage_service(session).build_universe(
                    operator_pinned=tuple(args.symbols) if args.symbols else None
                )
            elif args.command == "build-research-coverage-snapshot":
                result = await build_coverage_service(session).build_coverage_snapshot(
                    args.universe_id
                )
            elif args.command == "show-stock-coverage":
                result = await build_coverage_service(session).stock_coverage(args.symbol)
            elif args.command == "plan-coverage-backfill":
                result = await build_coverage_service(session).plan_backfill(
                    args.coverage_snapshot_id
                )
            elif args.command == "run-coverage-backfill":
                result = await build_coverage_service(session).run_backfill(args.run_id)
            elif args.command == "coverage-backfill-status":
                result = await build_coverage_service(session).backfill_status(args.run_id)
            elif args.command == "recover-coverage-backfill":
                result = await build_coverage_service(session).recover_interrupted_backfill(
                    args.run_id
                )
            elif args.command == "generate-beta-learning-report":
                result = await build_coverage_service(session).learning_report(args.days)
            elif args.command == "list-beta-feedback":
                result = await build_coverage_service(session).list_feedback(args.limit)
            elif args.command == "update-beta-feedback-status":
                result = await build_coverage_service(session).update_feedback_status(
                    args.feedback_id, args.status
                )
            elif args.command == "grant-operator":
                membership = await OperatorService(session, get_settings()).grant_operator(
                    args.email, args.role
                )
                result = {
                    "status": "granted",
                    "user_id": membership.user_id,
                    "role": membership.role,
                }
            elif args.command == "revoke-operator":
                revoked = await OperatorService(session, get_settings()).revoke_operator(args.email)
                result = {"status": "revoked" if revoked else "not_found"}
            elif args.command == "list-operators":
                rows = await OperatorService(session, get_settings()).list_operators()
                result = [
                    {
                        "user_id": membership.user_id,
                        "email": email,
                        "role": membership.role,
                        "created_at": membership.created_at,
                    }
                    for membership, email in rows
                ]
            elif args.command == "check-production-readiness":
                settings = get_settings()
                if settings.app_env != "production":
                    result = {
                        "status": "not_production_environment",
                        "environment": settings.app_env,
                    }
                else:
                    settings.validate_runtime_security()
                    await ProviderConfigurationService(
                        session, settings
                    ).validate_production_runtime()
                    result = {
                        "status": "configuration_valid",
                        "environment": settings.app_env,
                    }
            elif args.command == "generate-provider-encryption-key":
                result = {"key": generate_key()}
            elif args.command == "reencrypt-provider-credentials":
                settings = get_settings()
                if settings.provider_credential_active_key_id != args.to_key_id:
                    raise ValueError("target_key_must_be_active_key")
                operator = await session.scalar(
                    select(User).where(User.email == args.operator_email.strip().lower())
                )
                if operator is None:
                    raise ValueError("operator_not_found")
                count = await ProviderConfigurationService(session, settings).reencrypt_all(
                    operator.id
                )
                result = {"status": "reencrypted", "credential_count": count}
            elif args.command == "automation-tick":
                result = await build_automation_service(session).tick()
            elif args.command == "automation-run":
                automation = build_automation_service(session)
                triggered = await automation.trigger_run(args.policy_key)
                result = (
                    await automation.execute_run(triggered.run_id)
                    if triggered.status == "accepted"
                    else triggered
                )
            elif args.command == "automation-resume":
                automation = build_automation_service(session)
                resumed = await automation.resume_run(args.run_id)
                result = (
                    await automation.execute_run(resumed.run_id)
                    if resumed.status == "accepted"
                    else resumed
                )
            elif args.command == "automation-refresh-stock":
                automation = build_automation_service(session)
                triggered = await automation.trigger_run(symbols=(args.symbol,))
                result = (
                    await automation.execute_run(triggered.run_id)
                    if triggered.status == "accepted"
                    else triggered
                )
            else:
                result = await build_fundamental_service(session).compute_snapshot(
                    args.symbol, as_of=args.as_of
                )
            if hasattr(result, "model_dump"):
                payload = result.model_dump()
            elif is_dataclass(result):
                payload = asdict(result)
            elif isinstance(result, list):
                payload = [
                    item.model_dump() if hasattr(item, "model_dump") else item for item in result
                ]
            else:
                payload = result
            print(json.dumps(payload, default=str, ensure_ascii=False))
    finally:
        await engine.dispose()


def main() -> None:
    asyncio.run(_run(_parser().parse_args()))


if __name__ == "__main__":
    main()
