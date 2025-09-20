import unittest
from unittest.mock import MagicMock

import pandas as pd

from models import Position
from trader.trade_executor import TradeExecutor


class DummyNotifier:
    def __init__(self):
        self.messages = []

    def send(self, msg: str):
        self.messages.append(msg)


class TestOrderFlowsTimeoutAndAggregation(unittest.TestCase):
    def setUp(self):
        self.client = MagicMock()
        self.data_provider = MagicMock()
        self.state_manager = MagicMock()
        self.notifier = DummyNotifier()
        # Common klines df with ATR
        self.df = pd.DataFrame({
            "Open time": pd.to_datetime(["2023-01-01", "2023-01-02", "2023-01-03"]),
            "Open": [10, 11, 12],
            "High": [11, 12, 13],
            "Low": [9, 10, 11],
            "Close": [10.5, 11.5, 12.5],
            "Volume": [100, 100, 100],
            "atr": [0.5, 0.6, 0.7],
        })
        self.data_provider.get_and_update_klines.return_value = self.df

    def _make_executor(self, **kwargs) -> TradeExecutor:
        base_kwargs = {
            "client": self.client,
            "data_provider": self.data_provider,
            "state_manager": self.state_manager,
            "notifier": self.notifier,
            "execution_mode": "LIVE",
            "order_timeout_sec": 1,  # speed up polling loop
            "order_retry": 0,
        }
        base_kwargs.update(kwargs)
        return TradeExecutor(**base_kwargs)

    def test_live_buy_timeout_then_recent_orders_reports_filled(self):
        symbol = "BTCUSDT"
        positions = {}

        # Slippage guard ok
        self.client.get_orderbook_ticker.return_value = {"bidPrice": "100", "askPrice": "100.1"}

        # Initial create_order returns NEW with clientOrderId but no fills/orderId
        first_resp = {"status": "NEW", "clientOrderId": "cid-timeout"}
        self.client.create_order.return_value = first_resp

        # Polling always returns NEW until timeout
        self.client.get_order.return_value = {"status": "NEW", "clientOrderId": "cid-timeout"}

        # After timeout, recent orders contain a FILLED order with cumulative fields
        self.client.get_all_orders.return_value = [
            {
                "clientOrderId": "cid-timeout",
                "status": "FILLED",
                "orderId": 4242,
                "executedQty": "0.02",
                "cummulativeQuoteQty": "2.0",
            }
        ]

        ex = self._make_executor()
        # Make deterministic to match our get_all_orders entry
        ex._generate_client_order_id = lambda side, sym: "cid-timeout"

        ex.market_buy(symbol, usdt_to_spend=2.0, positions=positions, atr_multiplier=0.5, timeframe="5m")

        self.assertIn(symbol, positions)
        pos: Position = positions[symbol]
        self.assertGreater(pos.qty, 0)
        self.assertGreater(pos.entry_price, 0)
        self.assertTrue(any("(LIVE)" in m for m in self.notifier.messages))


if __name__ == "__main__":
    unittest.main()


