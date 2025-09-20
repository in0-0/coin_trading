import unittest
from unittest.mock import MagicMock

import pandas as pd

from trader.trade_executor import TradeExecutor


class DummyNotifier:
    def __init__(self):
        self.messages = []

    def send(self, msg: str):
        self.messages.append(msg)


class TestRetryIdempotency(unittest.TestCase):
    def setUp(self):
        self.client = MagicMock()
        self.data_provider = MagicMock()
        self.state_manager = MagicMock()
        self.notifier = DummyNotifier()
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
            "order_timeout_sec": 1,
            "order_retry": 0,
        }
        base_kwargs.update(kwargs)
        return TradeExecutor(**base_kwargs)

    def test_retry_reuses_client_order_id_and_single_fill(self):
        symbol = "ETHUSDT"
        positions = {}

        # Slippage ok
        self.client.get_orderbook_ticker.return_value = {"bidPrice": "100", "askPrice": "100.2"}

        # First create_order raises timeout/network error -> triggers status check by clientOrderId
        def _raise_timeout():
            raise Exception("timeout")

        self.client.create_order.side_effect = _raise_timeout

        # Recent orders show exactly one FILLED order with cumulative fields
        self.client.get_all_orders.return_value = [
            {
                "clientOrderId": "cid-stable",
                "status": "FILLED",
                "orderId": 999,
                "executedQty": "0.015",
                "cummulativeQuoteQty": "1.5",
            }
        ]

        ex = self._make_executor()
        ex._generate_client_order_id = lambda side, sym: "cid-stable"

        ex.market_buy(symbol, usdt_to_spend=1.5, positions=positions, atr_multiplier=0.5, timeframe="5m")

        # Ensure we didn't call create_order repeatedly with new IDs: only one attempt was made
        self.assertEqual(self.client.create_order.call_count, 1)
        # Position recorded with qty 0.015 and avg price 1.5/0.015 = 100
        self.assertIn(symbol, positions)
        pos = positions[symbol]
        self.assertAlmostEqual(pos.qty, 0.015, places=8)
        self.assertAlmostEqual(pos.entry_price, 100.0, places=6)


if __name__ == "__main__":
    unittest.main()


