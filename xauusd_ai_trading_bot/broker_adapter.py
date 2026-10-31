"""Safe broker adapter boundary for a future Exness MT5 desktop bridge.

The adapter is deliberately read-only and disconnected by default. It exposes
separate market-data, account-information, and order-execution capabilities so
future bridge work cannot accidentally turn a data check into an order path.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import math

from .mt5_bridge import (
    AccountInfoGateway,
    AccountMode,
    BrokerSafetyError,
    ConnectionStatus,
    DataOrigin,
    DisabledOrderExecution,
    MarketDataGateway,
    MT5DesktopBridgeClient,
    NotConnectedMT5DesktopBridgeClient,
    OrderExecutionGateway,
)

MAX_VERIFIED_QUOTE_AGE_SECONDS = 60


def _quote_is_verified(
    quote: object,
    expected_symbol: str,
) -> bool:
    """Accept only a fresh, real, structurally valid quote for the symbol."""

    try:
        quote_symbol = getattr(quote, "symbol")
        bid = float(getattr(quote, "bid"))
        ask = float(getattr(quote, "ask"))
        timestamp = datetime.fromisoformat(
            str(getattr(quote, "timestamp")).replace("Z", "+00:00")
        )
        data_origin = getattr(quote, "data_origin")
        if timestamp.tzinfo is None:
            return False
    except (AttributeError, TypeError, ValueError):
        return False

    now = datetime.now(timezone.utc)
    age = (now - timestamp.astimezone(timezone.utc)).total_seconds()
    return (
        isinstance(quote_symbol, str)
        and quote_symbol.upper() == expected_symbol.upper()
        and math.isfinite(bid)
        and math.isfinite(ask)
        and bid > 0
        and ask >= bid
        and data_origin is DataOrigin.REAL
        and -5 <= age <= MAX_VERIFIED_QUOTE_AGE_SECONDS
    )


class LiveModeLocked(BrokerSafetyError):
    """Raised because LIVE mode is not available in the current version."""


@dataclass(frozen=True)
class DemoSafetyConfig:
    """Demo defaults: no bridge orders and read-only market-data testing."""

    read_only_market_data: bool = True
    simulated_orders_only: bool = True
    execution_enabled: bool = False


@dataclass(frozen=True)
class LiveSafetyConfig:
    """Future live-release inputs; LIVE remains locked regardless of values."""

    enabled: bool = False
    explicit_confirmation_required: bool = True


@dataclass(frozen=True)
class AccountModeConfig:
    """Account mode and its separate safety controls."""

    mode: AccountMode = AccountMode.DEMO
    demo: DemoSafetyConfig = field(default_factory=DemoSafetyConfig)
    live: LiveSafetyConfig = field(default_factory=LiveSafetyConfig)

    def __post_init__(self) -> None:
        if self.mode is AccountMode.LIVE:
            raise LiveModeLocked(
                "LIVE mode is locked and disabled. A future release must add "
                "separate safety configuration and explicit confirmation."
            )
        if not self.demo.read_only_market_data:
            raise BrokerSafetyError(
                "Demo market-data mode must remain read-only in this version."
            )
        if not self.demo.simulated_orders_only:
            raise BrokerSafetyError(
                "Demo execution must be simulated-only in this version."
            )

    @classmethod
    def default(cls) -> "AccountModeConfig":
        return cls()


@dataclass(frozen=True)
class BrokerStatus:
    """Non-secret status data suitable for a dashboard."""

    account_mode: AccountMode
    connection_status: ConnectionStatus
    bridge_configured: bool
    symbol: str
    bid: float | None
    ask: float | None
    spread: float | None
    timestamp: str | None
    data_origin: DataOrigin
    market_data_read_only: bool
    demo_execution_enabled: bool
    live_mode_enabled: bool
    order_execution_allowed: bool
    message: str

    def to_dict(self) -> dict[str, object | None]:
        return {
            "account_mode": self.account_mode.value,
            "connection_status": self.connection_status.value,
            "bridge_configured": self.bridge_configured,
            "symbol": self.symbol,
            "bid": self.bid,
            "ask": self.ask,
            "spread": self.spread,
            "timestamp": self.timestamp,
            "data_origin": self.data_origin.value,
            "market_data_read_only": self.market_data_read_only,
            "demo_execution_enabled": self.demo_execution_enabled,
            "live_mode_enabled": self.live_mode_enabled,
            "order_execution_allowed": self.order_execution_allowed,
            "message": self.message,
        }


class BrokerAdapter:
    """Safe facade over the future bridge capabilities."""

    def __init__(
        self,
        bridge: MT5DesktopBridgeClient | None = None,
        config: AccountModeConfig | None = None,
    ) -> None:
        self.config = config or AccountModeConfig.default()
        self.bridge = bridge or NotConnectedMT5DesktopBridgeClient()
        self.market_data: MarketDataGateway = self.bridge.market_data
        self.account_info: AccountInfoGateway = self.bridge.account_info
        # Never expose a bridge order executor through the current adapter.
        self.order_execution: OrderExecutionGateway = DisabledOrderExecution()

    def status(self, symbol: str = "XAUUSD") -> BrokerStatus:
        """Return status only after a connected bridge returns a quote."""

        connection_status = self.bridge.connection_status
        quote = None
        message = (
            "MT5 desktop bridge is not configured. No live quote is available "
            "and no broker order can be sent."
        )

        if connection_status is ConnectionStatus.CONNECTED:
            if not self.bridge.bridge_configured:
                connection_status = ConnectionStatus.ERROR
                message = "Bridge reported connected without verified configuration."
            else:
                try:
                    candidate = self.market_data.get_quote(symbol.upper())
                except Exception:
                    connection_status = ConnectionStatus.ERROR
                    message = "Bridge quote verification failed; prices are hidden."
                else:
                    if _quote_is_verified(candidate, symbol):
                        quote = candidate
                        message = "Bridge verified with a fresh real market quote."
                    else:
                        connection_status = ConnectionStatus.ERROR
                        message = (
                            "Bridge quote is not verified as fresh real data; "
                            "prices are hidden."
                        )

        return BrokerStatus(
            account_mode=self.config.mode,
            connection_status=connection_status,
            bridge_configured=self.bridge.bridge_configured,
            symbol=quote.symbol if quote else symbol.upper(),
            bid=quote.bid if quote else None,
            ask=quote.ask if quote else None,
            spread=quote.spread if quote else None,
            timestamp=quote.timestamp if quote else None,
            data_origin=quote.data_origin if quote else DataOrigin.SIMULATED,
            market_data_read_only=self.config.demo.read_only_market_data,
            demo_execution_enabled=self.config.demo.execution_enabled,
            live_mode_enabled=self.config.live.enabled,
            order_execution_allowed=False,
            message=message,
        )


def create_default_broker_adapter() -> BrokerAdapter:
    """Create the disconnected DEMO adapter used by the current application."""

    return BrokerAdapter()