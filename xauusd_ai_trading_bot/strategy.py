"""Rule-based XAUUSD analysis and signal classification."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .indicators import calculate_indicators

SIGNALS = ("BUY", "SELL", "WAIT")


@dataclass(frozen=True)
class StrategyResult:
    """The strategy's classification and explainable evidence."""

    signal: str
    confidence: float
    reasons: tuple[str, ...]
    trend: str
    momentum: str
    breakout: str


def _latest_valid(data: pd.DataFrame, column: str) -> float | None:
    value = data[column].iloc[-1]
    return None if pd.isna(value) else float(value)


def analyze_market(data: pd.DataFrame) -> StrategyResult:
    """Analyze the latest candle and return only BUY, SELL, or WAIT.

    The rule set combines EMA alignment, RSI, MACD histogram, and a simple
    rolling-range breakout check. Missing warm-up values result in WAIT rather
    than an invented signal.
    """

    required = {
        "close",
        "high",
        "low",
        "ema_20",
        "ema_50",
        "rsi_14",
        "macd_histogram",
    }
    if not required.issubset(data.columns):
        data = calculate_indicators(data)
    if len(data) < 55:
        return StrategyResult(
            signal="WAIT",
            confidence=0.0,
            reasons=("At least 55 candles are required for indicator warm-up.",),
            trend="UNKNOWN",
            momentum="UNKNOWN",
            breakout="UNKNOWN",
        )

    latest = data.iloc[-1]
    prior = data.iloc[-2]
    values = {
        column: _latest_valid(data, column)
        for column in (
            "close",
            "ema_20",
            "ema_50",
            "rsi_14",
            "macd_histogram",
            "atr_pct",
        )
        if column in data.columns
    }
    if any(values.get(column) is None for column in ("close", "ema_20", "ema_50", "rsi_14", "macd_histogram")):
        return StrategyResult(
            signal="WAIT",
            confidence=0.0,
            reasons=("Indicator warm-up is incomplete.",),
            trend="UNKNOWN",
            momentum="UNKNOWN",
            breakout="UNKNOWN",
        )

    close = float(values["close"])
    ema_20 = float(values["ema_20"])
    ema_50 = float(values["ema_50"])
    rsi = float(values["rsi_14"])
    histogram = float(values["macd_histogram"])
    prior_histogram = float(prior["macd_histogram"])
    rolling_high = float(data["high"].iloc[-21:-1].max())
    rolling_low = float(data["low"].iloc[-21:-1].min())

    bullish_trend = close > ema_20 > ema_50
    bearish_trend = close < ema_20 < ema_50
    trend = "BULLISH" if bullish_trend else "BEARISH" if bearish_trend else "NEUTRAL"

    bullish_momentum = rsi >= 52 and histogram > 0
    bearish_momentum = rsi <= 48 and histogram < 0
    momentum = (
        "BULLISH"
        if bullish_momentum
        else "BEARISH"
        if bearish_momentum
        else "MIXED"
    )

    bullish_breakout = close > rolling_high and float(prior["close"]) <= rolling_high
    bearish_breakout = close < rolling_low and float(prior["close"]) >= rolling_low
    breakout = (
        "BULLISH"
        if bullish_breakout
        else "BEARISH"
        if bearish_breakout
        else "NONE"
    )

    reasons: list[str] = []
    bullish_score = 0
    bearish_score = 0
    if bullish_trend:
        bullish_score += 2
        reasons.append("Price is above EMA 20 and EMA 50.")
    elif bearish_trend:
        bearish_score += 2
        reasons.append("Price is below EMA 20 and EMA 50.")
    else:
        reasons.append("EMA trend alignment is mixed.")

    if bullish_momentum:
        bullish_score += 1
        reasons.append(f"Momentum is bullish (RSI {rsi:.1f}, MACD histogram positive).")
    elif bearish_momentum:
        bearish_score += 1
        reasons.append(f"Momentum is bearish (RSI {rsi:.1f}, MACD histogram negative).")
    else:
        reasons.append(f"Momentum is mixed (RSI {rsi:.1f}).")

    if bullish_breakout:
        bullish_score += 1
        reasons.append("Latest close broke above the prior 20-candle high.")
    elif bearish_breakout:
        bearish_score += 1
        reasons.append("Latest close broke below the prior 20-candle low.")
    else:
        reasons.append("No fresh 20-candle range breakout detected.")

    if histogram > 0 > prior_histogram:
        reasons.append("MACD histogram has just crossed above zero.")
    elif histogram < 0 < prior_histogram:
        reasons.append("MACD histogram has just crossed below zero.")

    if bullish_score >= 3 and bullish_score > bearish_score:
        signal = "BUY"
        score = bullish_score
    elif bearish_score >= 3 and bearish_score > bullish_score:
        signal = "SELL"
        score = bearish_score
    else:
        signal = "WAIT"
        score = max(bullish_score, bearish_score)
        reasons.append("Conditions are not aligned strongly enough for a directional signal.")

    confidence = round(min(0.99, score / 4), 2) if signal != "WAIT" else round(score / 4, 2)
    return StrategyResult(
        signal=signal,
        confidence=confidence,
        reasons=tuple(reasons),
        trend=trend,
        momentum=momentum,
        breakout=breakout,
    )