import argparse
import asyncio
import json
from dataclasses import asdict
from datetime import date, datetime

from zhaoniu_api.composition import (
    build_fundamental_service,
    build_market_data_service,
    build_research_service,
)
from zhaoniu_api.database import engine, session_factory
from zhaoniu_api.fundamentals.models import FundamentalSnapshot
from zhaoniu_api.market_data.service import SyncResult
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
    return parser


async def _run(args: argparse.Namespace) -> None:
    try:
        async with session_factory() as session:
            result: SyncResult | FundamentalSnapshot | ResearchBuildResult
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
