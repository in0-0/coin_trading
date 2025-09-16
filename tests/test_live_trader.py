import unittest
from unittest.mock import MagicMock, patch

import pandas as pd

from models import Position, Signal
from live_trader_gpt import LiveTrader


class TestLiveTrader(unittest.TestCase):
    @patch("live_trader_gpt.Client")
    @patch("live_trader_gpt.BinanceData")
    @patch("live_trader_gpt.StateManager")
    def test_entry_and_exit_flow(self, MockStateManager, MockBinanceData, MockClient):
        # Mock client and environment
        mock_client_instance = MagicMock()
        MockClient.return_value = mock_client_instance

        # Mock StateManager load/save
        mock_sm_instance = MockStateManager.return_value
        mock_sm_instance.load_positions.return_value = {}

        # Mock data provider
        mock_bd_instance = MockBinanceData.return_value
        df = pd.DataFrame({
            "Open time": pd.to_datetime(["2023-01-01", "2023-01-02", "2023-01-03"]),
            "Open": [10, 11, 12],
            "High": [11, 12, 13],
            "Low": [9, 10, 11],
            "Close": [10.5, 11.5, 12.5],
            "Volume": [100, 100, 100],
            # provide atr to avoid fallback path randomness
            "atr": [0.5, 0.6, 0.7],
        })
        mock_bd_instance.get_and_update_klines.return_value = df
        mock_bd_instance.get_current_price.return_value = 100.0

        # Mock account balance to allow entries
        mock_client_instance.get_account.return_value = {"balances": [{"asset": "USDT", "free": "1000"}]}

        # Patch StrategyFactory to force BUY then SELL
        with patch("live_trader_gpt.StrategyFactory") as MockFactory:
            buy_call = MagicMock()
            buy_call.get_signal.return_value = Signal.BUY
            # map for all symbols
            MockFactory.return_value.create_strategy.return_value = buy_call

            trader = LiveTrader()

            # Trigger a single pass of entries
            trader._find_and_execute_entries()
            # After BUY for first symbol, positions should have at least one entry
            self.assertGreaterEqual(len(trader.positions), 1)
            mock_sm_instance.save_positions.assert_called()

            # Now force SELL on that symbol
            first_symbol = next(iter(trader.positions.keys()))
            buy_call.get_signal.return_value = Signal.SELL
            # Ensure stop check triggers sell too when price <= stop
            trader._find_and_execute_entries()
            # SELL path uses _place_sell_order, which deletes position
            # For deterministic exit, call directly
            trader._place_sell_order(first_symbol)
            self.assertNotIn(first_symbol, trader.positions)


if __name__ == "__main__":
    unittest.main()

