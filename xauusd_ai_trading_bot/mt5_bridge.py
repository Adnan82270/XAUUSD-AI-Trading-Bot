"""Interfaces for a future MT5 desktop bridge.

This module intentionally contains no MetaTrader5 import, socket client, or
credential handling. A Windows/VPS bridge can implement these protocols later.
The current implementations are explicit safe defaults that cannot connect or
send broker orders.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol


class BrokerSafetyError(RuntimeError):
    """Raised when an operation would cross the current safety boundary."""


class BridgeNotConfigured(BrokerSafetyError):
    """Raised when a desktop bridge has not been configured."""


class AccountMode(str, Enum):
    DEMO = "DEMO"
    LIVE = "LIVE"


class ConnectionStatus(str, Enum):
    NOT_CONNECTED = "NOT_CONNECTED"
    CONNECTED = "CONNECTED"
    ERROR = "ERROR"


class DataOrigin(str, Enum):
    REAL = "REAL"
    SIMULATED = "SIMULATED"


@dataclass(frozen=True)
class MarketQuote:
    """A broker quote returned by a future bridge implementation."""

    symbol: str
    bid: float
    ask: float
    timestamp: str
    data_origin: DataOrigin = DataOrigin.REAL

    @property
    def spread(self) -> float:
        return self.ask - self.bid


@dataclass(frozen=True)
class AccountInfo:
    """Non-secret account information returned by a future bridge."""

    account_mode: AccountMode
    broker_name: str | None = None
    account_id: str | None = None
    balance: float | None = None
    currency: str | None = None


@dataclass(frozen=True)
class OrderRequest:
    """A future order request shape; it is not executable in this version."""

    symbol: str
    direction: str
    volume: float
    stop_loss: float | None = None
    take_profit: float | None = None


@dataclass(frozen=True)
class OrderReceipt:
    """Result shape reserved for a future simulated or bridge executor."""

    order_id: str
    status: str
    simulated: bool


class MarketDataGateway(Protocol):
    """Market-data capability exposed by a future desktop bridge."""

    def get_quote(self, symbol: str) -> MarketQuote:
        ...


class AccountInfoGateway(Protocol):
    """Account-information capability exposed by a future desktop bridge."""

    def get_account_info(self) -> AccountInfo:
        ...


class OrderExecutionGateway(Protocol):
    """Order capability kept separate from market data and account info."""

    def submit(self, request: OrderRequest) -> OrderReceipt:
        ...


class MT5DesktopBridgeClient(Protocol):
    """Interface a Windows MT5 desktop/VPS bridge can implement later."""

    @property
    def connection_status(self) -> ConnectionStatus:
        ...

    @property
    def bridge_configured(self) -> bool:
        ...

    @property
    def market_data(self) -> MarketDataGateway:
        ...

    @property
    def account_info(self) -> AccountInfoGateway:
        ...

    @property
    def order_execution(self) -> OrderExecutionGateway:
        ...

    def connect(self) -> None:
        ...

    def disconnect(self) -> None:
        ...


class _NotConnectedMarketData:
    def get_quote(self, symbol: str) -> MarketQuote:
        raise BridgeNotConfigured(
            "MT5 desktop bridge is not configured; market data is unavailable."
        )


class _NotConnectedAccountInfo:
    def get_account_info(self) -> AccountInfo:
        raise BridgeNotConfigured(
            "MT5 desktop bridge is not configured; account information is unavailable."
        )


class DisabledOrderExecution:
    """Hard stop: no current code path can send a broker order."""

    def submit(self, request: OrderRequest) -> OrderReceipt:
        raise BrokerSafetyError(
            "Order execution is disabled in this version; no broker order can be sent."
        )


@dataclass(frozen=True)
class NotConnectedMT5DesktopBridgeClient:
    """Safe placeholder until a Windows/VPS bridge is explicitly implemented."""

    _market_data: MarketDataGateway = field(
        default_factory=_NotConnectedMarketData,
        repr=False,
    )
    _account_info: AccountInfoGateway = field(
        default_factory=_NotConnectedAccountInfo,
        repr=False,
    )
    _order_execution: OrderExecutionGateway = field(
        default_factory=DisabledOrderExecution,
        repr=False,
    )

    @property
    def connection_status(self) -> ConnectionStatus:
        return ConnectionStatus.NOT_CONNECTED

    @property
    def bridge_configured(self) -> bool:
        return False

    @property
    def market_data(self) -> MarketDataGateway:
        return self._market_data

    @property
    def account_info(self) -> AccountInfoGateway:
        return self._account_info

    @property
    def order_execution(self) -> OrderExecutionGateway:
        return self._order_execution

    def connect(self) -> None:
        raise BridgeNotConfigured(
            "No MT5 desktop bridge is configured. Replit cannot connect directly "
            "to an MT5 desktop terminal."
        )

    def disconnect(self) -> None:
        return None