import unittest
from unittest.mock import MagicMock

import pandas as pd

from trader.trade_executor import TradeExecutor


class DummyNotifier:
    def __init__(self):
        self.messages = []

    def send(self, msg: str):
        self.messages.append(msg)


class TestPartialFillsAggregation(unittest.TestCase):
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

    def test_partial_fills_are_aggregated_correctly(self):
        symbol = "BTCUSDT"
        positions = {}

        # Slippage guard passes
        self.client.get_orderbook_ticker.return_value = {"bidPrice": "100", "askPrice": "100.1"}

        # create_order returns FILLED with two fills
        resp = {
            "status": "FILLED",
            "orderId": 111,
            "clientOrderId": "cid-partial",
            "fills": [
                {"price": "100.00", "qty": "0.01000000", "commission": "0.00001000", "commissionAsset": "BTC"},
                {"price": "102.00", "qty": "0.02000000", "commission": "0.00002000", "commissionAsset": "BTC"},
            ],
        }
        self.client.create_order.return_value = resp

        ex = self._make_executor()
        ex._generate_client_order_id = lambda side, sym: "cid-partial"

        ex.market_buy(symbol, usdt_to_spend=3.0, positions=positions, atr_multiplier=0.5, timeframe="5m")

        self.assertIn(symbol, positions)
        pos = positions[symbol]
        # total qty = 0.01 + 0.02 = 0.03
        self.assertAlmostEqual(pos.qty, 0.03, places=8)
        # weighted avg = (100*0.01 + 102*0.02)/0.03 = (1 + 2.04)/0.03 = 3.04/0.03 ≈ 101.333333...
        self.assertAlmostEqual(pos.entry_price, 101.3333333333, places=6)
        # notifier should include LIVE
        self.assertTrue(any("(LIVE)" in m for m in self.notifier.messages))


if __name__ == "__main__":
    unittest.main()


