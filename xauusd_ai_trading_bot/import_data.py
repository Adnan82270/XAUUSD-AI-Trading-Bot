"""Validate and summarize a user-supplied historical candle CSV."""

from __future__ import annotations

import argparse
from pathlib import Path

from .market_data import (
    MIN_BACKTEST_CANDLES,
    MarketDataError,
    load_csv,
    resolve_csv_path,
    summarize_candles,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate and summarize a historical XAUUSD OHLCV CSV."
    )
    parser.add_argument(
        "--csv",
        type=Path,
        required=True,
        help="Path to a user-supplied historical OHLCV CSV.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    csv_path = resolve_csv_path(args.csv)
    try:
        candles = load_csv(csv_path)
        summary = summarize_candles(candles)
    except (FileNotFoundError, MarketDataError, ValueError) as error:
        print(f"CSV import failed: {error}")
        return 1

    print("=" * 72)
    print("XAUUSD HISTORICAL CSV IMPORT VALIDATION")
    print("=" * 72)
    print(f"CSV path    : {csv_path}")
    print("Source      : user-supplied CSV; authenticity is not verified.")
    print(f"First candle : {summary.first_timestamp}")
    print(f"Last candle  : {summary.last_timestamp}")
    print(f"Total candles: {summary.candle_count}")
    if summary.candle_count >= MIN_BACKTEST_CANDLES:
        print(f"Backtest status: READY ({MIN_BACKTEST_CANDLES}+ candles)")
    else:
        print(
            f"Backtest status: NOT READY "
            f"({MIN_BACKTEST_CANDLES} candles required)"
        )
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())