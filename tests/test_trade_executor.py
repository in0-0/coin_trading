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


class TestTradeExecutorLive(unittest.TestCase):
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
        # Defaults for live mode tests; allow kwargs to override without duplication
        base_kwargs = {
            "client": self.client,
            "data_provider": self.data_provider,
            "state_manager": self.state_manager,
            "notifier": self.notifier,
            "execution_mode": "LIVE",
        }
        base_kwargs.update(kwargs)
        return TradeExecutor(**base_kwargs)

    def test_live_buy_with_partial_fill_then_poll_to_filled(self):
        symbol = "BTCUSDT"
        positions = {}

        # Slippage guard ok
        self.client.get_orderbook_ticker.return_value = {"bidPrice": "100", "askPrice": "100.2"}

        # Initial create_order returns NEW with no fills
        first_resp = {"status": "NEW", "clientOrderId": "abc"}
        self.client.create_order.return_value = first_resp

        # Polling returns FILLED with cumulative fields
        self.client.get_order.return_value = {
            "status": "FILLED",
            "orderId": 123,
            "executedQty": "0.05",
            "cummulativeQuoteQty": "5.0",
        }

        ex = self._make_executor()
        ex.market_buy(symbol, usdt_to_spend=5.0, positions=positions, atr_multiplier=0.5, timeframe="5m")

        self.assertIn(symbol, positions)
        pos: Position = positions[symbol]
        self.assertGreater(pos.qty, 0)
        self.assertGreater(pos.entry_price, 0)
        # Notification includes LIVE marker
        self.assertTrue(any("(LIVE)" in m for m in self.notifier.messages))

    def test_live_sell_with_rules_rounding_and_min_notional(self):
        symbol = "ETHUSDT"
        positions = {symbol: Position(symbol, qty=0.123456, entry_price=1500.0, stop_price=1400.0)}

        # Slippage guard ok and bid price for notional
        self.client.get_orderbook_ticker.return_value = {"bidPrice": "1500", "askPrice": "1500.3"}
        # Symbol filters
        self.client.get_symbol_info.return_value = {
            "filters": [
                {"filterType": "LOT_SIZE", "stepSize": "0.00100000", "minQty": "0.00100000"},
                {"filterType": "MIN_NOTIONAL", "minNotional": "5"},
                {"filterType": "PRICE_FILTER", "tickSize": "0.01000000"},
            ]
        }
        # create_order returns FULL with fills list
        self.client.create_order.return_value = {
            "status": "FILLED",
            "orderId": 777,
            "fills": [
                {"price": "1500.00", "qty": "0.06", "commission": "0.1", "commissionAsset": "USDT"},
                {"price": "1500.10", "qty": "0.06", "commission": "0.1", "commissionAsset": "USDT"},
            ],
        }

        ex = self._make_executor()
        ex.market_sell(symbol, positions)

        self.assertNotIn(symbol, positions)
        self.assertTrue(any("SELL" in m for m in self.notifier.messages))

    def test_slippage_guard_blocks_order(self):
        symbol = "SOLUSDT"
        positions = {}
        # Spread too wide
        self.client.get_orderbook_ticker.return_value = {"bidPrice": "100", "askPrice": "101"}

        ex = self._make_executor(max_slippage_bps=5)
        ex.market_buy(symbol, usdt_to_spend=10.0, positions=positions, atr_multiplier=0.5, timeframe="5m")
        self.assertNotIn(symbol, positions)
        self.assertTrue(any("Skipping BUY" in m for m in self.notifier.messages))

    def test_idempotency_via_recent_orders_lookup_on_failure(self):
        symbol = "BNBUSDT"
        positions = {}
        # Slippage ok
        self.client.get_orderbook_ticker.return_value = {"bidPrice": "300", "askPrice": "300.05"}
        # First create_order raises, then get_all_orders returns a matching clientOrderId with FILLED
        self.client.create_order.side_effect = [Exception("net"), {"status": "FILLED", "clientOrderId": "cid1", "executedQty": "0.01", "cummulativeQuoteQty": "3"}]
        self.client.get_all_orders.return_value = [{"clientOrderId": "cid1", "status": "FILLED", "executedQty": "0.01", "cummulativeQuoteQty": "3"}]

        # Make client_order_id deterministic to match returned one
        ex = self._make_executor()
        ex._generate_client_order_id = lambda side, sym: "cid1"

        ex.market_buy(symbol, usdt_to_spend=3.0, positions=positions, atr_multiplier=0.5, timeframe="5m")

        self.assertIn(symbol, positions)


if __name__ == "__main__":
    unittest.main()


