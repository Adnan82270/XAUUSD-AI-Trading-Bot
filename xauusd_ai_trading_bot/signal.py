"""Structured analysis signal generation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from .risk import RiskConfig, calculate_reference_levels
from .strategy import analyze_market


@dataclass(frozen=True)
class Signal:
    """A serialisable, analysis-only signal report."""

    symbol: str
    timeframe: str
    signal: str
    entry_reference_price: float
    stop_loss: float | None
    take_profit: float | None
    confidence_score: float
    reasons: tuple[str, ...]
    timestamp: str
    trend: str
    momentum: str
    breakout: str

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly representation."""

        return asdict(self)


def generate_signal(
    data: pd.DataFrame,
    symbol: str = "XAUUSD",
    timeframe: str = "H1",
    risk_config: RiskConfig | None = None,
) -> Signal:
    """Generate one latest-candle signal without sending an order."""

    if not symbol.strip():
        raise ValueError("symbol cannot be empty.")
    if not timeframe.strip():
        raise ValueError("timeframe cannot be empty.")
    if data.empty:
        raise ValueError("Cannot generate a signal from empty market data.")

    strategy = analyze_market(data)
    entry_price = float(data["close"].iloc[-1])
    atr_value = data["atr_14"].iloc[-1] if "atr_14" in data else None
    atr = None if pd.isna(atr_value) else float(atr_value)
    levels = calculate_reference_levels(
        entry_price=entry_price,
        atr=atr,
        direction=strategy.signal if strategy.signal in ("BUY", "SELL") else "BUY",
        config=risk_config,
    )

    return Signal(
        symbol=symbol.upper(),
        timeframe=timeframe.upper(),
        signal=strategy.signal,
        entry_reference_price=round(entry_price, 2),
        stop_loss=levels.stop_loss if strategy.signal != "WAIT" else None,
        take_profit=levels.take_profit if strategy.signal != "WAIT" else None,
        confidence_score=strategy.confidence,
        reasons=strategy.reasons,
        timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        trend=strategy.trend,
        momentum=strategy.momentum,
        breakout=strategy.breakout,
    )