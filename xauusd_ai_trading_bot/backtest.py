"""Historical, analysis-only backtesting engine.

The engine deliberately has no broker or order-management integration. It
walks through validated candles in chronological order, evaluates the
strategy on a prefix ending at each signal candle, and enters on the next
candle's open.
"""

from __future__ import annotations

import argparse
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

import pandas as pd

from .indicators import calculate_indicators
from .market_data import (
    CandleSummary,
    MarketDataError,
    ensure_minimum_candles,
    load_csv,
    resolve_csv_path,
    summarize_candles,
)
from .risk import RiskConfig, calculate_reference_levels
from .strategy import analyze_market

Direction = Literal["BUY", "SELL"]
EXIT_REASONS = ("STOP_LOSS", "TAKE_PROFIT", "END_OF_DATA")
TRADE_COLUMNS = (
    "trade_id",
    "symbol",
    "timeframe",
    "direction",
    "signal_time",
    "entry_time",
    "exit_time",
    "signal_price",
    "entry_price",
    "stop_loss",
    "take_profit",
    "exit_price",
    "exit_reason",
    "bars_held",
    "confidence",
    "gross_pnl",
    "transaction_costs",
    "net_pnl",
    "balance_after",
)


@dataclass(frozen=True)
class BacktestConfig:
    """Simulation settings.

    ``spread`` and ``slippage`` are price units for XAUUSD. For example, a
    spread of ``0.20`` represents a 20-cent full bid/ask spread. Slippage is
    adverse price movement per fill. Position sizing is fixed units because
    this engine does not connect to an account or calculate lot risk.
    """

    initial_balance: float = 10_000.0
    units: float = 1.0
    spread: float = 0.0
    slippage: float = 0.0
    symbol: str = "XAUUSD"
    timeframe: str = "H1"
    risk_config: RiskConfig = field(default_factory=RiskConfig)

    def __post_init__(self) -> None:
        if self.initial_balance <= 0:
            raise ValueError("initial_balance must be positive.")
        if self.units <= 0:
            raise ValueError("units must be positive.")
        if self.spread < 0:
            raise ValueError("spread cannot be negative.")
        if self.slippage < 0:
            raise ValueError("slippage cannot be negative.")
        if not self.symbol.strip():
            raise ValueError("symbol cannot be empty.")
        if not self.timeframe.strip():
            raise ValueError("timeframe cannot be empty.")


@dataclass(frozen=True)
class Trade:
    """One completed simulated trade."""

    trade_id: int
    symbol: str
    timeframe: str
    direction: Direction
    signal_time: str
    entry_time: str
    exit_time: str
    signal_price: float
    entry_price: float
    stop_loss: float
    take_profit: float
    exit_price: float
    exit_reason: str
    bars_held: int
    confidence: float
    gross_pnl: float
    transaction_costs: float
    net_pnl: float
    balance_after: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BacktestMetrics:
    """Summary statistics calculated from completed trades."""

    total_trades: int
    wins: int
    losses: int
    win_rate: float
    net_pnl: float
    max_drawdown: float
    max_drawdown_pct: float
    profit_factor: float
    average_win: float
    average_loss: float
    final_balance: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BacktestResult:
    """Completed backtest and its trade-by-trade results."""

    initial_balance: float
    candles_analyzed: int
    trades: tuple[Trade, ...]
    metrics: BacktestMetrics

    def trade_dataframe(self) -> pd.DataFrame:
        """Return the trade report in stable CSV column order."""

        rows = [trade.to_dict() for trade in self.trades]
        return pd.DataFrame(rows, columns=TRADE_COLUMNS)

    def write_trade_csv(self, path: str | Path) -> Path:
        """Write the completed simulated trades to a CSV report."""

        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        self.trade_dataframe().to_csv(output_path, index=False)
        return output_path


@dataclass(frozen=True)
class _PendingSignal:
    signal_index: int
    signal_time: str
    signal_price: float
    direction: Direction
    stop_loss: float
    take_profit: float
    confidence: float


@dataclass(frozen=True)
class _OpenTrade:
    trade_id: int
    pending: _PendingSignal
    entry_index: int
    entry_time: str
    entry_market_price: float
    entry_price: float


def _timestamp(value: object) -> str:
    """Convert a validated candle timestamp into a stable ISO string."""

    return pd.Timestamp(value).isoformat()


def _fill_price(
    market_price: float,
    direction: Direction,
    is_entry: bool,
    config: BacktestConfig,
) -> float:
    """Apply half-spread and adverse slippage to a simulated fill."""

    adverse_cost = config.spread / 2 + config.slippage
    if direction == "BUY":
        return market_price + adverse_cost if is_entry else market_price - adverse_cost
    return market_price - adverse_cost if is_entry else market_price + adverse_cost


def _resolve_exit(
    position: _OpenTrade,
    candle: pd.Series,
) -> tuple[float, str] | None:
    """Return the first modeled exit in an OHLC candle.

    OHLC data does not reveal the intrabar path. When both levels are touched,
    stop loss is intentionally checked first as the conservative assumption.
    """

    low = float(candle["low"])
    high = float(candle["high"])
    stop_hit = (
        low <= position.pending.stop_loss
        if position.pending.direction == "BUY"
        else high >= position.pending.stop_loss
    )
    target_hit = (
        high >= position.pending.take_profit
        if position.pending.direction == "BUY"
        else low <= position.pending.take_profit
    )

    if stop_hit:
        return position.pending.stop_loss, "STOP_LOSS"
    if target_hit:
        return position.pending.take_profit, "TAKE_PROFIT"
    return None


def _close_trade(
    position: _OpenTrade,
    exit_index: int,
    exit_time: str,
    raw_exit_price: float,
    exit_reason: str,
    config: BacktestConfig,
    balance_before: float,
) -> Trade:
    direction_multiplier = 1 if position.pending.direction == "BUY" else -1
    gross_pnl = (
        (raw_exit_price - position.entry_market_price)
        * direction_multiplier
        * config.units
    )
    transaction_costs = (config.spread + 2 * config.slippage) * config.units
    net_pnl = gross_pnl - transaction_costs
    exit_price = _fill_price(
        raw_exit_price,
        position.pending.direction,
        is_entry=False,
        config=config,
    )

    return Trade(
        trade_id=position.trade_id,
        symbol=config.symbol.upper(),
        timeframe=config.timeframe.upper(),
        direction=position.pending.direction,
        signal_time=position.pending.signal_time,
        entry_time=position.entry_time,
        exit_time=exit_time,
        signal_price=round(position.pending.signal_price, 5),
        entry_price=round(position.entry_price, 5),
        stop_loss=round(position.pending.stop_loss, 5),
        take_profit=round(position.pending.take_profit, 5),
        exit_price=round(exit_price, 5),
        exit_reason=exit_reason,
        bars_held=exit_index - position.entry_index + 1,
        confidence=position.pending.confidence,
        gross_pnl=round(gross_pnl, 5),
        transaction_costs=round(transaction_costs, 5),
        net_pnl=round(net_pnl, 5),
        balance_after=round(balance_before + net_pnl, 5),
    )


def _mark_to_market(
    balance: float,
    position: _OpenTrade | None,
    close: float,
    config: BacktestConfig,
) -> float:
    """Estimate closed balance plus current position equity for drawdown."""

    if position is None:
        return balance
    direction_multiplier = 1 if position.pending.direction == "BUY" else -1
    unrealized = (
        (close - position.entry_market_price)
        * direction_multiplier
        * config.units
    )
    round_trip_costs = (config.spread + 2 * config.slippage) * config.units
    return balance + unrealized - round_trip_costs


def _metrics(
    trades: list[Trade],
    initial_balance: float,
    equity_curve: list[float],
) -> BacktestMetrics:
    profits = [trade.net_pnl for trade in trades if trade.net_pnl > 0]
    losses = [trade.net_pnl for trade in trades if trade.net_pnl <= 0]
    total_trades = len(trades)
    wins = len(profits)
    gross_profit = sum(profits)
    gross_loss = sum(losses)
    peak = initial_balance
    max_drawdown = 0.0

    for equity in equity_curve:
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, peak - equity)

    final_balance = (
        trades[-1].balance_after if trades else initial_balance
    )
    profit_factor = (
        gross_profit / abs(gross_loss)
        if gross_loss < 0
        else math.inf
        if gross_profit > 0
        else 0.0
    )
    return BacktestMetrics(
        total_trades=total_trades,
        wins=wins,
        losses=len(losses),
        win_rate=(wins / total_trades * 100) if total_trades else 0.0,
        net_pnl=round(final_balance - initial_balance, 5),
        max_drawdown=round(max_drawdown, 5),
        max_drawdown_pct=round(
            max_drawdown / initial_balance * 100, 5
        ),
        profit_factor=round(profit_factor, 5)
        if math.isfinite(profit_factor)
        else math.inf,
        average_win=round(sum(profits) / len(profits), 5) if profits else 0.0,
        average_loss=round(sum(losses) / len(losses), 5) if losses else 0.0,
        final_balance=round(final_balance, 5),
    )


def run_backtest(
    candles: pd.DataFrame,
    config: BacktestConfig | None = None,
) -> BacktestResult:
    """Run a sequential, next-candle-entry backtest.

    A signal at index ``i`` is generated from ``candles.iloc[:i + 1]`` only.
    Its simulated entry is scheduled for index ``i + 1``. The prefix is
    recalculated on every signal evaluation so the no-look-ahead boundary is
    visible in the implementation rather than relying on a full-data cache.
    """

    settings = config or BacktestConfig()
    data = ensure_minimum_candles(candles)
    trades: list[Trade] = []
    equity_curve = [settings.initial_balance]
    balance = settings.initial_balance
    pending: _PendingSignal | None = None
    position: _OpenTrade | None = None
    next_trade_id = 1

    for index in range(len(data)):
        candle = data.iloc[index]
        candle_time = _timestamp(candle["time"])

        if pending is not None:
            entry_market_price = float(candle["open"])
            position = _OpenTrade(
                trade_id=next_trade_id,
                pending=pending,
                entry_index=index,
                entry_time=candle_time,
                entry_market_price=entry_market_price,
                entry_price=_fill_price(
                    entry_market_price,
                    pending.direction,
                    is_entry=True,
                    config=settings,
                ),
            )
            pending = None
            next_trade_id += 1

        if position is not None:
            exit_trigger = _resolve_exit(position, candle)
            if exit_trigger is not None:
                raw_exit_price, exit_reason = exit_trigger
                trade = _close_trade(
                    position=position,
                    exit_index=index,
                    exit_time=candle_time,
                    raw_exit_price=raw_exit_price,
                    exit_reason=exit_reason,
                    config=settings,
                    balance_before=balance,
                )
                balance = trade.balance_after
                trades.append(trade)
                position = None

        # A final candle cannot generate a usable next-candle entry.
        if position is None and pending is None and index < len(data) - 1:
            # Only this prefix is visible to the strategy at this close.
            visible_candles = data.iloc[: index + 1]
            visible_indicators = calculate_indicators(visible_candles)
            strategy = analyze_market(visible_indicators)
            atr_value = visible_indicators["atr_14"].iloc[-1]

            if (
                strategy.signal in ("BUY", "SELL")
                and not pd.isna(atr_value)
            ):
                signal_price = float(visible_candles["close"].iloc[-1])
                levels = calculate_reference_levels(
                    entry_price=signal_price,
                    atr=float(atr_value),
                    direction=strategy.signal,
                    config=settings.risk_config,
                )
                if levels.stop_loss is not None and levels.take_profit is not None:
                    pending = _PendingSignal(
                        signal_index=index,
                        signal_time=candle_time,
                        signal_price=signal_price,
                        direction=strategy.signal,
                        stop_loss=levels.stop_loss,
                        take_profit=levels.take_profit,
                        confidence=strategy.confidence,
                    )

        equity_curve.append(
            _mark_to_market(
                balance=balance,
                position=position,
                close=float(candle["close"]),
                config=settings,
            )
        )

    # No position is carried beyond the data window. If it survived the last
    # candle, close it at that candle's close for a deterministic report.
    if position is not None:
        last_index = len(data) - 1
        last_candle = data.iloc[last_index]
        trade = _close_trade(
            position=position,
            exit_index=last_index,
            exit_time=_timestamp(last_candle["time"]),
            raw_exit_price=float(last_candle["close"]),
            exit_reason="END_OF_DATA",
            config=settings,
            balance_before=balance,
        )
        balance = trade.balance_after
        trades.append(trade)
        equity_curve.append(balance)

    return BacktestResult(
        initial_balance=settings.initial_balance,
        candles_analyzed=len(data),
        trades=tuple(trades),
        metrics=_metrics(
            trades=trades,
            initial_balance=settings.initial_balance,
            equity_curve=equity_curve,
        ),
    )


def _format_number(value: float) -> str:
    return "inf" if math.isinf(value) else f"{value:,.2f}"


def print_report(
    result: BacktestResult,
    output_path: Path,
    candle_summary: CandleSummary,
    data_source: str,
) -> None:
    """Print a readable simulation report."""

    metrics = result.metrics
    print("=" * 72)
    print("XAUUSD HISTORICAL BACKTEST — SIMULATION ONLY")
    print("=" * 72)
    print("Safety: no real or demo trades are placed, modified, or closed.")
    print("Warning: historical results do not guarantee future performance.")
    print(f"Data source      : {data_source}")
    print(f"First candle     : {candle_summary.first_timestamp}")
    print(f"Last candle      : {candle_summary.last_timestamp}")
    print(f"Candles analyzed : {candle_summary.candle_count}")
    print(f"Total trades     : {metrics.total_trades}")
    print(f"Wins / losses    : {metrics.wins} / {metrics.losses}")
    print(f"Win rate         : {metrics.win_rate:.2f}%")
    print(f"Net P/L          : {_format_number(metrics.net_pnl)}")
    print(f"Max drawdown     : {_format_number(metrics.max_drawdown)} ({metrics.max_drawdown_pct:.2f}%)")
    print(f"Profit factor    : {_format_number(metrics.profit_factor)}")
    print(f"Average win      : {_format_number(metrics.average_win)}")
    print(f"Average loss     : {_format_number(metrics.average_loss)}")
    print(f"Final balance    : {_format_number(metrics.final_balance)}")
    print(f"Trade report     : {output_path}")
    print("=" * 72)


def print_preflight(candle_summary: CandleSummary, csv_path: Path) -> None:
    """Print the validated file facts before the simulation starts."""

    print("=" * 72)
    print("BACKTEST CSV PREFLIGHT")
    print("=" * 72)
    print(f"CSV path      : {csv_path}")
    print(f"Candle count  : {candle_summary.candle_count}")
    print(f"First candle  : {candle_summary.first_timestamp}")
    print(f"Last candle   : {candle_summary.last_timestamp}")
    print("Validation    : passed; starting analysis-only backtest")
    print("=" * 72)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run an analysis-only historical XAUUSD backtest."
    )
    parser.add_argument(
        "--csv",
        type=Path,
        required=True,
        help="User-supplied historical OHLCV CSV path.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("backtest_trades.csv"),
        help="Trade report CSV path (default: backtest_trades.csv).",
    )
    parser.add_argument(
        "--initial-balance",
        type=float,
        default=10_000.0,
        help="Starting balance for reporting (default: 10000).",
    )
    parser.add_argument(
        "--units",
        type=float,
        default=1.0,
        help="Fixed simulated position size in units (default: 1).",
    )
    parser.add_argument(
        "--spread",
        type=float,
        default=0.0,
        help="Full spread in XAUUSD price units, e.g. 0.20 (default: 0).",
    )
    parser.add_argument(
        "--slippage",
        type=float,
        default=0.0,
        help="Adverse slippage per fill in price units (default: 0).",
    )
    parser.add_argument(
        "--timeframe",
        default="H1",
        help="Timeframe label for the report (default: H1).",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    csv_path = resolve_csv_path(args.csv)
    try:
        candles = ensure_minimum_candles(load_csv(csv_path))
        candle_summary = summarize_candles(candles)
        config = BacktestConfig(
            initial_balance=args.initial_balance,
            units=args.units,
            spread=args.spread,
            slippage=args.slippage,
            timeframe=args.timeframe,
        )
        print_preflight(candle_summary, csv_path)
        result = run_backtest(candles, config)
        output_path = result.write_trade_csv(args.output)
        print_report(
            result=result,
            output_path=output_path,
            candle_summary=candle_summary,
            data_source=f"user-supplied CSV: {csv_path}",
        )
    except (FileNotFoundError, MarketDataError, ValueError) as error:
        print(f"Backtest failed: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())