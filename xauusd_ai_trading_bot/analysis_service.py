"""Optional, analysis-only worker for the dashboard.

The worker reuses the project's existing indicators and strategy against the
bundled synthetic development sample. It emits JSON snapshots only and never
includes a quote or reference price that could be mistaken for live pricing.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import threading
import time
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from .indicators import calculate_indicators
from .market_data import load_sample_data, validate_candles
from .signal import generate_signal

SAMPLE_SOURCE = "bundled synthetic sample data (not live market data)"
VERIFIED_SOURCE = "authenticated MT5 DEMO bridge (XAUUSDm M5)"
MAX_QUOTE_AGE_SECONDS = 15
MAX_CANDLE_AGE_SECONDS = 10 * 60
MAX_FUTURE_SKEW_SECONDS = 5

_latest_market_data: dict[str, Any] | None = None
_market_data_lock = threading.Lock()
_market_data_received = threading.Event()


def _parse_aware_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _validated_fresh_bridge_candles(
    market_data: dict[str, Any] | None,
    now: datetime | None = None,
) -> pd.DataFrame | None:
    """Accept only the narrow, recent quote/candle payload from the API."""

    if not isinstance(market_data, dict) or set(market_data) != {
        "symbol",
        "timestamp",
        "bid",
        "ask",
        "candles",
    }:
        return None
    if market_data.get("symbol") != "XAUUSDm":
        return None

    quote_time = _parse_aware_timestamp(market_data.get("timestamp"))
    now_utc = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if quote_time is None:
        return None
    quote_age = (now_utc - quote_time).total_seconds()
    if not -MAX_FUTURE_SKEW_SECONDS <= quote_age <= MAX_QUOTE_AGE_SECONDS:
        return None

    try:
        bid = float(market_data["bid"])
        ask = float(market_data["ask"])
    except (TypeError, ValueError):
        return None
    if not math.isfinite(bid) or not math.isfinite(ask) or bid <= 0 or ask < bid:
        return None

    rows = market_data.get("candles")
    if not isinstance(rows, list) or len(rows) != 100:
        return None
    expected_candle_keys = {"time", "open", "high", "low", "close", "volume"}
    if any(not isinstance(row, dict) or set(row) != expected_candle_keys for row in rows):
        return None
    for row in rows:
        candle_time = _parse_aware_timestamp(row.get("time"))
        if candle_time is None or int(candle_time.timestamp()) % 300 != 0:
            return None
        try:
            candle_values = [
                float(row[key]) for key in ("open", "high", "low", "close", "volume")
            ]
        except (TypeError, ValueError):
            return None
        if not all(math.isfinite(value) for value in candle_values):
            return None
    last_candle_time = _parse_aware_timestamp(rows[-1].get("time"))
    if last_candle_time is None:
        return None
    candle_age = (now_utc - last_candle_time).total_seconds()
    if not -MAX_FUTURE_SKEW_SECONDS <= candle_age <= MAX_CANDLE_AGE_SECONDS:
        return None

    try:
        candles = validate_candles(pd.DataFrame(rows))
    except (TypeError, ValueError):
        return None
    return candles if len(candles) == 100 else None


def build_analysis_snapshot(
    market_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Analyze fresh authenticated demo candles, otherwise labeled sample data."""

    candles = _validated_fresh_bridge_candles(market_data)
    is_verified_demo_feed = candles is not None
    if candles is None:
        candles = load_sample_data()
        symbol = "XAUUSD"
        timeframe = "H1"
        source = SAMPLE_SOURCE
    else:
        symbol = "XAUUSDm"
        timeframe = "M5"
        source = VERIFIED_SOURCE

    enriched = calculate_indicators(candles)
    signal = generate_signal(enriched, symbol=symbol, timeframe=timeframe)
    return {
        "symbol": symbol,
        "signal": signal.signal,
        "trend": signal.trend,
        "momentum": signal.momentum,
        "confidence": signal.confidence_score,
        "breakout": signal.breakout,
        "timestamp": signal.timestamp,
        "source": source if is_verified_demo_feed else SAMPLE_SOURCE,
        "candleCount": len(candles),
        "reasons": list(signal.reasons),
    }


def _read_market_data_updates(stream: Any) -> None:
    """Read one-way JSON updates from the API; no broker commands are accepted."""

    global _latest_market_data
    for line in stream:
        if not line.strip():
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            print("Ignored malformed market-data update.", file=sys.stderr, flush=True)
            continue
        if isinstance(message, dict):
            with _market_data_lock:
                _latest_market_data = message
            _market_data_received.set()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run analysis-only XAUUSD snapshots for the dashboard."
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=15,
        help="Seconds between analysis snapshots (default: 15).",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.interval < 1:
        print("Analysis interval must be at least one second.")
        return 2

    threading.Thread(
        target=_read_market_data_updates,
        args=(sys.stdin,),
        daemon=True,
    ).start()
    # The API writes its latest verified snapshot as soon as the worker starts.
    # Give that pipe a short chance to arrive before the first analysis tick.
    _market_data_received.wait(timeout=min(0.5, float(args.interval)))

    try:
        while True:
            with _market_data_lock:
                current_market_data = _latest_market_data
            snapshot = build_analysis_snapshot(current_market_data)
            print(json.dumps(snapshot, separators=(",", ":")), flush=True)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
