import argparse
import asyncio
import json
from dataclasses import asdict
from datetime import date, datetime

from zhaoniu_api.ai_research.models import AIResearchBuildResult
from zhaoniu_api.composition import (
    build_ai_research_service,
    build_fundamental_service,
    build_market_data_service,
    build_peer_research_service,
    build_research_service,
)
from zhaoniu_api.database import engine, session_factory
from zhaoniu_api.fundamentals.models import FundamentalSnapshot
from zhaoniu_api.market_data.service import SyncResult
from zhaoniu_api.peer_research.models import PeerBuildResult
from zhaoniu_api.peer_research.service import IndustrySyncResult
from zhaoniu_api.research.models import ResearchBuildResult


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
            )
            if args.command == "sync-stock-master":
                result = await build_market_data_service(session).sync_stock_master(
                    force=args.force
                )
            elif args.command == "sync-daily-bars":
                result = await build_market_data_service(session).sync_daily_bars(
                    args.symbol, start=args.start, end=args.end, force=args.force
                )
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
            else:
                result = await build_fundamental_service(session).compute_snapshot(
                    args.symbol, as_of=args.as_of
                )
            print(json.dumps(asdict(result), default=str, ensure_ascii=False))
    finally:
        await engine.dispose()


def main() -> None:
    asyncio.run(_run(_parser().parse_args()))


if __name__ == "__main__":
    main()
