import argparse
import asyncio
import json
from dataclasses import asdict
from datetime import date

from zhaoniu_api.composition import build_market_data_service
from zhaoniu_api.database import engine, session_factory


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
    return parser


async def _run(args: argparse.Namespace) -> None:
    try:
        async with session_factory() as session:
            service = build_market_data_service(session)
            if args.command == "sync-stock-master":
                result = await service.sync_stock_master(force=args.force)
            else:
                result = await service.sync_daily_bars(
                    args.symbol, start=args.start, end=args.end, force=args.force
                )
            print(json.dumps(asdict(result), default=str, ensure_ascii=False))
    finally:
        await engine.dispose()


def main() -> None:
    asyncio.run(_run(_parser().parse_args()))


if __name__ == "__main__":
    main()
