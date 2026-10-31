"""Technical indicator calculations implemented with pandas."""

from __future__ import annotations

import pandas as pd


class IndicatorError(ValueError):
    """Raised when indicator input is not suitable for calculation."""


def _require_columns(candles: pd.DataFrame) -> None:
    if candles.empty:
        raise IndicatorError("Cannot calculate indicators for empty data.")
    missing = {"high", "low", "close"} - set(candles.columns)
    if missing:
        raise IndicatorError(
            f"Indicator input is missing columns: {', '.join(sorted(missing))}."
        )


def calculate_indicators(candles: pd.DataFrame) -> pd.DataFrame:
    """Return candles enriched with EMA, RSI, ATR, MACD, and volatility fields."""

    _require_columns(candles)
    data = candles.copy()
    close = data["close"].astype(float)
    high = data["high"].astype(float)
    low = data["low"].astype(float)

    data["ema_20"] = close.ewm(span=20, adjust=False, min_periods=20).mean()
    data["ema_50"] = close.ewm(span=50, adjust=False, min_periods=50).mean()

    delta = close.diff()
    gains = delta.clip(lower=0)
    losses = -delta.clip(upper=0)
    average_gain = gains.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    average_loss = losses.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    relative_strength = average_gain / average_loss.replace(0, float("nan"))
    data["rsi_14"] = 100 - (100 / (1 + relative_strength))
    data.loc[(average_loss == 0) & (average_gain > 0), "rsi_14"] = 100.0
    data.loc[(average_loss == 0) & (average_gain == 0), "rsi_14"] = 50.0

    previous_close = close.shift(1)
    true_range = pd.concat(
        [
            high - low,
            (high - previous_close).abs(),
            (low - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    data["true_range"] = true_range
    data["atr_14"] = true_range.ewm(
        alpha=1 / 14, adjust=False, min_periods=14
    ).mean()

    ema_12 = close.ewm(span=12, adjust=False, min_periods=12).mean()
    ema_26 = close.ewm(span=26, adjust=False, min_periods=26).mean()
    data["macd"] = ema_12 - ema_26
    data["macd_signal"] = data["macd"].ewm(
        span=9, adjust=False, min_periods=9
    ).mean()
    data["macd_histogram"] = data["macd"] - data["macd_signal"]

    data["return_pct"] = close.pct_change() * 100
    data["volatility_20"] = data["return_pct"].rolling(20, min_periods=20).std()
    data["atr_pct"] = (data["atr_14"] / close) * 100
    data["range_pct"] = ((high - low) / close) * 100

    return data