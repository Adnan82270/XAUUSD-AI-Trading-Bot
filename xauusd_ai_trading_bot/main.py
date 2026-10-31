"""Command-line entry point for the analysis-only XAUUSD bot."""

from __future__ import annotations

import argparse
from pathlib import Path

from .indicators import calculate_indicators
from .market_data import MarketDataError, load_csv, load_sample_data
from .signal import Signal, generate_signal


def _format_price(value: float | None) -> str:
    return "N/A" if value is None else f"{value:,.2f}"


def print_report(
    signal: Signal,
    candles_count: int,
    data_source: str,
) -> None:
    """Print a readable, explicitly analysis-only market report."""

    print("=" * 68)
    print("XAUUSD AI TRADING ANALYSIS — RULE-BASED / ANALYSIS ONLY")
    print("=" * 68)
    print("Safety: no trades are placed, modified, or closed by this program.")
    print(f"Data source        : {data_source}")
    print(f"Symbol / timeframe : {signal.symbol} / {signal.timeframe}")
    print(f"Candles analyzed   : {candles_count}")
    print(f"Signal             : {signal.signal}")
    print(f"Reference price    : {_format_price(signal.entry_reference_price)}")
    print(f"Stop loss (ref.)   : {_format_price(signal.stop_loss)}")
    print(f"Take profit (ref.) : {_format_price(signal.take_profit)}")
    print(f"Confidence         : {signal.confidence_score:.0%}")
    print(f"Trend / momentum   : {signal.trend} / {signal.momentum}")
    print(f"Breakout           : {signal.breakout}")
    print(f"Timestamp (UTC)    : {signal.timestamp}")
    print("Reasons:")
    for reason in signal.reasons:
        print(f"  - {reason}")
    print("=" * 68)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate an analysis-only XAUUSD signal from OHLCV CSV data."
    )
    parser.add_argument(
        "--csv",
        type=Path,
        help="Optional OHLCV CSV path. Defaults to bundled sample XAUUSD data.",
    )
    parser.add_argument(
        "--timeframe",
        default="H1",
        help="Timeframe label for the report (default: H1).",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        candles = load_csv(args.csv) if args.csv else load_sample_data()
        enriched = calculate_indicators(candles)
        latest_signal = generate_signal(
            enriched,
            symbol="XAUUSD",
            timeframe=args.timeframe,
        )
        data_source = (
            f"user-supplied CSV: {args.csv}"
            if args.csv
            else "bundled synthetic sample data"
        )
        print_report(latest_signal, len(enriched), data_source)
    except (FileNotFoundError, MarketDataError, ValueError) as error:
        print(f"Analysis failed: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())