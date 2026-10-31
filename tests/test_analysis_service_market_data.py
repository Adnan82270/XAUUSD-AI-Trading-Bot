"""Tests for analysis source selection from authenticated bridge inputs."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from xauusd_ai_trading_bot.analysis_service import (
    SAMPLE_SOURCE,
    VERIFIED_SOURCE,
    build_analysis_snapshot,
)


def make_bridge_payload(quote_age_seconds: int = 0) -> dict[str, object]:
    now = datetime.now(timezone.utc)
    latest_candle = now.replace(
        minute=(now.minute // 5) * 5, second=0, microsecond=0
    )
    candles = []
    for index in range(100):
        close = 2300.0 + index * 0.1
        candles.append(
            {
                "time": (latest_candle - timedelta(minutes=(99 - index) * 5)).isoformat(),
                "open": close - 0.05,
                "high": close + 0.1,
                "low": close - 0.1,
                "close": close,
                "volume": 100 + index,
            }
        )
    return {
        "symbol": "XAUUSDm",
        "timestamp": (now - timedelta(seconds=quote_age_seconds)).isoformat(),
        "bid": 2300.1,
        "ask": 2300.3,
        "candles": candles,
    }


class AnalysisServiceMarketDataTests(unittest.TestCase):
    def test_fresh_bridge_candles_use_existing_analysis_and_are_labeled(self) -> None:
        snapshot = build_analysis_snapshot(make_bridge_payload())

        self.assertEqual(snapshot["source"], VERIFIED_SOURCE)
        self.assertEqual(snapshot["symbol"], "XAUUSDm")
        self.assertEqual(snapshot["candleCount"], 100)
        self.assertIn(snapshot["signal"], {"BUY", "SELL", "WAIT"})
        self.assertNotIn("price", snapshot)
        self.assertNotIn("entry_reference_price", snapshot)

    def test_stale_bridge_quote_falls_back_to_explicitly_labeled_sample(self) -> None:
        snapshot = build_analysis_snapshot(make_bridge_payload(quote_age_seconds=20))

        self.assertEqual(snapshot["source"], SAMPLE_SOURCE)
        self.assertEqual(snapshot["symbol"], "XAUUSD")
        self.assertNotIn("price", snapshot)

    def test_bridge_payload_with_non_finite_candle_is_not_used(self) -> None:
        payload = make_bridge_payload()
        candles = payload["candles"]
        assert isinstance(candles, list)
        candles[-1]["close"] = float("inf")

        snapshot = build_analysis_snapshot(payload)

        self.assertEqual(snapshot["source"], SAMPLE_SOURCE)


if __name__ == "__main__":
    unittest.main()
