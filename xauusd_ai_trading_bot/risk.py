"""Analysis-only ATR risk level calculations.

This module calculates reference levels. It intentionally has no broker,
account, position, or order-management code.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Direction = Literal["BUY", "SELL"]


@dataclass(frozen=True)
class RiskConfig:
    """Configurable reference-level settings.

    ``risk_percentage`` is optional and intentionally defaults to ``None``:
    no account sizing is calculated unless a future caller explicitly opts in.
    """

    risk_percentage: float | None = None
    stop_loss_atr_multiple: float = 1.5
    take_profit_atr_multiple: float = 3.0

    def __post_init__(self) -> None:
        if self.risk_percentage is not None and not (
            0 < self.risk_percentage <= 100
        ):
            raise ValueError("risk_percentage must be between 0 and 100.")
        if self.stop_loss_atr_multiple <= 0:
            raise ValueError("stop_loss_atr_multiple must be positive.")
        if self.take_profit_atr_multiple <= 0:
            raise ValueError("take_profit_atr_multiple must be positive.")


@dataclass(frozen=True)
class ReferenceLevels:
    """Reference stop-loss and take-profit prices for a hypothetical setup."""

    stop_loss: float | None
    take_profit: float | None
    atr: float | None


def calculate_reference_levels(
    entry_price: float,
    atr: float | None,
    direction: Direction,
    config: RiskConfig | None = None,
) -> ReferenceLevels:
    """Calculate ATR-based levels without creating or managing a trade."""

    settings = config or RiskConfig()
    if entry_price <= 0:
        raise ValueError("entry_price must be positive.")
    if direction not in ("BUY", "SELL"):
        raise ValueError("direction must be BUY or SELL.")
    if atr is None:
        return ReferenceLevels(stop_loss=None, take_profit=None, atr=None)
    if atr <= 0:
        raise ValueError("atr must be positive when provided.")

    stop_distance = atr * settings.stop_loss_atr_multiple
    target_distance = atr * settings.take_profit_atr_multiple
    if direction == "BUY":
        stop_loss = entry_price - stop_distance
        take_profit = entry_price + target_distance
    else:
        stop_loss = entry_price + stop_distance
        take_profit = entry_price - target_distance

    return ReferenceLevels(
        stop_loss=round(stop_loss, 2),
        take_profit=round(take_profit, 2),
        atr=round(atr, 2),
    )