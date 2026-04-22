from __future__ import annotations

import argparse
import asyncio

from config import load_settings
from pump_system.app import TradingApplication


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Binance smallcap first pump entry + stop system")
    parser.add_argument(
        "command",
        nargs="?",
        default="run",
        choices=("run", "backfill", "validate"),
        help="run service, backfill only, or validate wiring",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    settings = load_settings()
    app = TradingApplication(settings)

    if args.command == "backfill":
        asyncio.run(app.backfill_only())
        return
    if args.command == "validate":
        asyncio.run(app.validate_only())
        return
    asyncio.run(app.run())


if __name__ == "__main__":
    main()
