"""Safety tests for the disconnected broker boundary."""

from __future__ import annotations

import unittest

from xauusd_ai_trading_bot.analysis_service import (
    SAMPLE_SOURCE,
    build_analysis_snapshot,
)
from xauusd_ai_trading_bot.broker_adapter import (
    AccountModeConfig,
    BrokerAdapter,
    LiveModeLocked,
)
from xauusd_ai_trading_bot.mt5_bridge import (
    AccountMode,
    BrokerSafetyError,
    ConnectionStatus,
    DataOrigin,
    MarketQuote,
    NotConnectedMT5DesktopBridgeClient,
    OrderRequest,
)


class BrokerAdapterSafetyTests(unittest.TestCase):
    def test_dashboard_analysis_is_synthetic_and_has_no_price(self) -> None:
        snapshot = build_analysis_snapshot()

        self.assertEqual(snapshot["source"], SAMPLE_SOURCE)
        self.assertIn(snapshot["signal"], {"BUY", "SELL", "WAIT"})
        self.assertIn("trend", snapshot)
        self.assertIn("momentum", snapshot)
        self.assertIn("confidence", snapshot)
        self.assertNotIn("price", snapshot)
        self.assertNotIn("entry_reference_price", snapshot)

    def test_default_adapter_is_demo_and_not_connected(self) -> None:
        status = BrokerAdapter().status()

        self.assertEqual(status.account_mode, AccountMode.DEMO)
        self.assertEqual(status.connection_status, ConnectionStatus.NOT_CONNECTED)
        self.assertFalse(status.bridge_configured)
        self.assertFalse(status.order_execution_allowed)
        self.assertIsNone(status.bid)
        self.assertIsNone(status.ask)

    def test_default_order_executor_rejects_every_order(self) -> None:
        adapter = BrokerAdapter()

        with self.assertRaisesRegex(
            BrokerSafetyError,
            "no broker order can be sent",
        ):
            adapter.order_execution.submit(
                OrderRequest(symbol="XAUUSD", direction="BUY", volume=1.0)
            )

    def test_live_mode_is_locked_even_when_requested(self) -> None:
        with self.assertRaises(LiveModeLocked):
            AccountModeConfig(mode=AccountMode.LIVE)

    def test_bridge_connection_is_not_available_in_current_version(self) -> None:
        with self.assertRaisesRegex(BrokerSafetyError, "cannot connect directly"):
            BrokerAdapter().bridge.connect()

    def test_connected_flag_without_a_quote_is_not_verified(self) -> None:
        class UnverifiedBridge(NotConnectedMT5DesktopBridgeClient):
            @property
            def connection_status(self) -> ConnectionStatus:
                return ConnectionStatus.CONNECTED

            @property
            def bridge_configured(self) -> bool:
                return True

        status = BrokerAdapter(bridge=UnverifiedBridge()).status()

        self.assertEqual(status.connection_status, ConnectionStatus.ERROR)
        self.assertIsNone(status.bid)
        self.assertEqual(status.data_origin, DataOrigin.SIMULATED)

    def test_prices_are_hidden_for_simulated_bridge_quote(self) -> None:
        class QuoteGateway:
            def get_quote(self, symbol: str) -> MarketQuote:
                return MarketQuote(
                    symbol=symbol,
                    bid=2300.0,
                    ask=2300.2,
                    timestamp=__import__("datetime").datetime.now(
                        __import__("datetime").timezone.utc
                    ).isoformat(),
                    data_origin=DataOrigin.SIMULATED,
                )

        class ConnectedBridge(NotConnectedMT5DesktopBridgeClient):
            @property
            def connection_status(self) -> ConnectionStatus:
                return ConnectionStatus.CONNECTED

            @property
            def bridge_configured(self) -> bool:
                return True

            @property
            def market_data(self) -> QuoteGateway:
                return QuoteGateway()

        status = BrokerAdapter(bridge=ConnectedBridge()).status()

        self.assertEqual(status.connection_status, ConnectionStatus.ERROR)
        self.assertIsNone(status.bid)
        self.assertIsNone(status.ask)
        self.assertEqual(status.data_origin, DataOrigin.SIMULATED)

    def test_only_fresh_real_bridge_quote_can_expose_price(self) -> None:
        from datetime import datetime, timezone

        class QuoteGateway:
            def get_quote(self, symbol: str) -> MarketQuote:
                return MarketQuote(
                    symbol=symbol,
                    bid=2300.0,
                    ask=2300.2,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    data_origin=DataOrigin.REAL,
                )

        class ConnectedBridge(NotConnectedMT5DesktopBridgeClient):
            @property
            def connection_status(self) -> ConnectionStatus:
                return ConnectionStatus.CONNECTED

            @property
            def bridge_configured(self) -> bool:
                return True

            @property
            def market_data(self) -> QuoteGateway:
                return QuoteGateway()

        status = BrokerAdapter(bridge=ConnectedBridge()).status()

        self.assertEqual(status.connection_status, ConnectionStatus.CONNECTED)
        self.assertEqual(status.bid, 2300.0)
        self.assertEqual(status.ask, 2300.2)
        self.assertEqual(status.data_origin, DataOrigin.REAL)

    def test_invalid_real_quote_values_are_hidden(self) -> None:
        from datetime import datetime, timezone

        class QuoteGateway:
            def get_quote(self, symbol: str) -> MarketQuote:
                return MarketQuote(
                    symbol=symbol,
                    bid=float("inf"),
                    ask=float("inf"),
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    data_origin=DataOrigin.REAL,
                )

        class ConnectedBridge(NotConnectedMT5DesktopBridgeClient):
            @property
            def connection_status(self) -> ConnectionStatus:
                return ConnectionStatus.CONNECTED

            @property
            def bridge_configured(self) -> bool:
                return True

            @property
            def market_data(self) -> QuoteGateway:
                return QuoteGateway()

        status = BrokerAdapter(bridge=ConnectedBridge()).status()

        self.assertEqual(status.connection_status, ConnectionStatus.ERROR)
        self.assertIsNone(status.bid)
        self.assertIsNone(status.ask)


if __name__ == "__main__":
    unittest.main()