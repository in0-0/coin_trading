import unittest
from unittest.mock import patch

import pandas as pd

from models import Position, Signal
from strategies.atr_trailing_stop_strategy import ATRTrailingStopStrategy


class TestATRTrailingStopStrategy(unittest.TestCase):
    def setUp(self):
        self.symbol = "BTCUSDT"
        self.strategy = ATRTrailingStopStrategy(symbol=self.symbol, atr_multiplier=1.0, risk_per_trade=0.01)

    @patch("pandas_ta.rsi")
    @patch("pandas_ta.atr")
    def test_buy_signal_when_rsi_low_and_no_position(self, mock_atr, mock_rsi):
        df = pd.DataFrame({
            "Open time": pd.to_datetime(["2023-01-01", "2023-01-02", "2023-01-03"]),
            "Open": [10, 11, 12],
            "High": [11, 12, 13],
            "Low": [9, 10, 11],
            "Close": [10.5, 11.5, 12.5],
            "Volume": [100, 100, 100],
        })
        mock_atr.return_value = pd.Series([0.5, 0.6, 0.7])
        mock_rsi.return_value = pd.Series([50, 40, 25])  # Latest RSI < 30 → BUY

        signal = self.strategy.get_signal(df.copy(), position=None)
        self.assertEqual(signal, Signal.BUY)

    @patch("pandas_ta.rsi")
    @patch("pandas_ta.atr")
    def test_sell_signal_on_stop_hit_for_open_long(self, mock_atr, mock_rsi):
        df = pd.DataFrame({
            "Open time": pd.to_datetime(["2023-01-01", "2023-01-02", "2023-01-03"]),
            "Open": [10, 11, 12],
            "High": [11, 12, 13],
            "Low": [9, 10, 11],
            "Close": [10.5, 9.0, 8.5],  # Drop below stop
            "Volume": [100, 100, 100],
        })
        mock_atr.return_value = pd.Series([0.5, 0.6, 0.7])
        mock_rsi.return_value = pd.Series([50, 40, 35])

        position = Position(symbol=self.symbol, qty=1.0, entry_price=10.0, stop_price=9.5)
        signal = self.strategy.get_signal(df.copy(), position=position)
        self.assertEqual(signal, Signal.SELL)

    @patch("pandas_ta.rsi")
    @patch("pandas_ta.atr")
    def test_hold_when_conditions_not_met(self, mock_atr, mock_rsi):
        df = pd.DataFrame({
            "Open time": pd.to_datetime(["2023-01-01", "2023-01-02", "2023-01-03"]),
            "Open": [10, 11, 12],
            "High": [11, 12, 13],
            "Low": [9, 10, 11],
            "Close": [10.5, 11.0, 11.2],
            "Volume": [100, 100, 100],
        })
        mock_atr.return_value = pd.Series([0.5, 0.6, 0.7])
        mock_rsi.return_value = pd.Series([50, 40, 50])

        position = Position(symbol=self.symbol, qty=1.0, entry_price=10.0, stop_price=8.0)
        signal = self.strategy.get_signal(df.copy(), position=position)
        self.assertEqual(signal, Signal.HOLD)


if __name__ == "__main__":
    unittest.main()

