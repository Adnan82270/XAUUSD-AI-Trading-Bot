"""Market data loading and validation.

The loader accepts CSV files now and keeps the interface small enough to
replace with an MT5 data adapter later without changing the analysis engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd

REQUIRED_COLUMNS = ("time", "open", "high", "low", "close", "volume")
NUMERIC_COLUMNS = ("open", "high", "low", "close", "volume")
PRICE_COLUMNS = ("open", "high", "low", "close")
MIN_BACKTEST_CANDLES = 500


class MarketDataError(ValueError):
    """Raised when candle data is missing, malformed, or inconsistent."""


@dataclass(frozen=True)
class CandleSummary:
    """Human-readable facts about a validated candle file."""

    candle_count: int
    first_timestamp: str
    last_timestamp: str

    def to_dict(self) -> dict[str, object]:
        return {
            "candle_count": self.candle_count,
            "first_timestamp": self.first_timestamp,
            "last_timestamp": self.last_timestamp,
        }


def _normalise_columns(columns: Iterable[object]) -> dict[object, str]:
    """Map common CSV header variations to the canonical column names."""

    aliases = {
        "datetime": "time",
        "date": "time",
        "timestamp": "time",
        "tick_volume": "volume",
    }
    mapping: dict[object, str] = {}
    for raw_column in columns:
        original = raw_column
        normalised = str(raw_column).strip().lower().replace(" ", "_")
        mapping[original] = aliases.get(normalised, normalised)
    return mapping


def validate_candles(candles: pd.DataFrame) -> pd.DataFrame:
    """Validate and return a clean, chronologically ordered OHLCV frame."""

    if candles.empty:
        raise MarketDataError("Candle data is empty.")

    cleaned = candles.copy()
    cleaned.columns = [
        str(column).strip().lower().replace(" ", "_")
        for column in cleaned.columns
    ]
    cleaned = cleaned.rename(columns=_normalise_columns(cleaned.columns))

    missing = [column for column in REQUIRED_COLUMNS if column not in cleaned]
    if missing:
        raise MarketDataError(
            f"Missing required candle columns: {', '.join(missing)}."
        )

    cleaned["time"] = pd.to_datetime(cleaned["time"], errors="coerce", utc=True)
    if cleaned["time"].isna().any():
        raise MarketDataError("Candle data contains invalid timestamps.")

    for column in NUMERIC_COLUMNS:
        cleaned[column] = pd.to_numeric(cleaned[column], errors="coerce")
    if cleaned[list(NUMERIC_COLUMNS)].isna().any().any():
        raise MarketDataError("Candle data contains non-numeric OHLCV values.")

    if (cleaned[list(PRICE_COLUMNS)] <= 0).any().any():
        raise MarketDataError("OHLC prices must all be greater than zero.")
    if (cleaned["volume"] < 0).any():
        raise MarketDataError("Volume cannot be negative.")
    if (cleaned["high"] < cleaned[["open", "close", "low"]].max(axis=1)).any():
        raise MarketDataError("Each candle high must contain open, close, and low.")
    if (cleaned["low"] > cleaned[["open", "close", "high"]].min(axis=1)).any():
        raise MarketDataError("Each candle low must contain open, close, and high.")

    duplicate_times = cleaned["time"].duplicated(keep=False)
    if duplicate_times.any():
        duplicates = cleaned.loc[duplicate_times, "time"].dt.strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ).unique()
        preview = ", ".join(duplicates[:3])
        suffix = "..." if len(duplicates) > 3 else ""
        raise MarketDataError(
            f"Duplicate candle timestamps are not allowed: {preview}{suffix}"
        )

    time_deltas = cleaned["time"].diff().dropna()
    if (time_deltas <= pd.Timedelta(0)).any():
        raise MarketDataError(
            "Candle timestamps must be strictly increasing in CSV order."
        )

    cleaned = cleaned.loc[:, list(REQUIRED_COLUMNS)].reset_index(drop=True)
    if len(cleaned) < 2:
        raise MarketDataError("At least two candles are required.")
    return cleaned


def summarize_candles(candles: pd.DataFrame) -> CandleSummary:
    """Return count and boundary timestamps for validated candles."""

    cleaned = validate_candles(candles)
    return CandleSummary(
        candle_count=len(cleaned),
        first_timestamp=cleaned["time"].iloc[0].isoformat(),
        last_timestamp=cleaned["time"].iloc[-1].isoformat(),
    )


def ensure_minimum_candles(
    candles: pd.DataFrame,
    minimum: int = MIN_BACKTEST_CANDLES,
) -> pd.DataFrame:
    """Require enough validated history for a meaningful backtest."""

    cleaned = validate_candles(candles)
    if len(cleaned) < minimum:
        raise MarketDataError(
            f"Backtesting requires at least {minimum} candles; "
            f"received {len(cleaned)}. Import a longer historical CSV."
        )
    return cleaned


def resolve_csv_path(path: str | Path) -> Path:
    """Resolve a user-provided CSV path to an absolute path."""

    return Path(path).expanduser().resolve()


def load_csv(path: str | Path) -> pd.DataFrame:
    """Load and validate OHLCV candles from a CSV path."""

    csv_path = resolve_csv_path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file does not exist: {csv_path}")
    if not csv_path.is_file():
        raise MarketDataError(f"Market data path is not a file: {csv_path}")
    try:
        return validate_candles(pd.read_csv(csv_path))
    except pd.errors.EmptyDataError as error:
        raise MarketDataError(f"Market data file is empty: {csv_path}") from error
    except pd.errors.ParserError as error:
        raise MarketDataError(f"Could not parse market data CSV: {csv_path}") from error


def load_sample_data() -> pd.DataFrame:
    """Load the bundled deterministic synthetic XAUUSD hourly data."""

    return load_csv(Path(__file__).parent / "data" / "sample_xauusd.csv")