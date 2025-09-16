import unittest
import pandas as pd
from backtester import Backtester
from position_sizer import AllInSizer


class TestBacktester(unittest.TestCase):
    def setUp(self):
        # Sample DataFrame with signals for backtesting
        self.df = pd.DataFrame(
            {
                "Open time": pd.to_datetime(
                    [f"2023-01-{i + 1:02d}" for i in range(10)]
                ),
                "Open": [10, 11, 12, 13, 14, 15, 16, 17, 18, 19],
                "High": [12, 13, 14, 15, 16, 17, 18, 19, 20, 21],
                "Low": [9, 10, 11, 12, 13, 14, 15, 16, 17, 18],
                "Close": [11, 12, 13, 14, 15, 16, 17, 18, 19, 20],
                "Volume": [100, 110, 120, 130, 140, 150, 160, 170, 180, 190],
                "Signal": [
                    0,
                    1,
                    0,
                    0,
                    0,
                    -1,
                    0,
                    1,
                    0,
                    -1,
                ],  # Buy on 2nd, Sell on 6th, Buy on 8th, Sell on 10th
            }
        )
        self.position_sizer = AllInSizer()

    def test_initialization(self):
        bt = Backtester(initial_capital=5000, position_sizer=self.position_sizer)
        self.assertEqual(bt.initial_capital, 5000)
        self.assertEqual(bt.cash, 5000)
        self.assertEqual(bt.position_size, 0)
        self.assertEqual(len(bt.trades), 0)

    def test_buy_and_sell_signals(self):
        bt = Backtester(initial_capital=1000, position_sizer=self.position_sizer)
        df_test = self.df.copy()
        df_test["Signal"] = [0, 1, 0, 0, 0, -1, 0, 0, 0, 0]  # Simple buy then sell
        report = bt.run(df_test)

        trades_df = report["trades"]
        self.assertGreater(len(trades_df), 0)
        self.assertEqual(trades_df.iloc[0]["type"], "BUY")
        self.assertEqual(
            trades_df.iloc[0]["entry_price"], 12
        )  # Close price at index 1
        self.assertEqual(
            trades_df.iloc[0]["exit_price"], 16
        )  # Close price at index 5
        self.assertEqual(trades_df.iloc[0]["type"], "SELL SIGNAL")

        # Check final value after a simple trade
        # Buy 1000/12 = 83.33 units. Sell 83.33 * 16 = 1333.33
        self.assertAlmostEqual(float(report["summary"]["Final Portfolio Value"].replace("$", "").replace(",", "")), 1333.33, places=2)

    def test_take_profit(self):
        bt = Backtester(initial_capital=1000, position_sizer=self.position_sizer)
        df_test = self.df.copy()
        df_test["Signal"] = [0, 1, 0, 0, 0, 0, 0, 0, 0, 0]  # Only buy signal
        # Manually adjust prices to trigger TP
        df_test.loc[2, "High"] = df_test.loc[1, "Close"] * 1.11  # Trigger TP at index 2
        report = bt.run(df_test, take_profit_pct=0.10)

        trades_df = report["trades"]
        self.assertEqual(trades_df.iloc[0]["type"], "TAKE PROFIT")
        self.assertAlmostEqual(
            trades_df.iloc[0]["exit_price"], 12 * 1.10
        )  # 12 (entry) * 1.10

    def test_stop_loss(self):
        bt = Backtester(initial_capital=1000, position_sizer=self.position_sizer)
        df_test = self.df.copy()
        df_test["Signal"] = [0, 1, 0, 0, 0, 0, 0, 0, 0, 0]  # Only buy signal
        # Manually adjust prices to trigger SL
        df_test.loc[2, "Low"] = df_test.loc[1, "Close"] * 0.94  # Trigger SL at index 2
        report = bt.run(df_test, stop_loss_pct=0.05)

        trades_df = report["trades"]
        self.assertEqual(trades_df.iloc[0]["type"], "STOP LOSS")
        self.assertAlmostEqual(
            trades_df.iloc[0]["exit_price"], 12 * 0.95
        )  # 12 (entry) * 0.95

    def test_time_cut(self):
        bt = Backtester(initial_capital=1000, position_sizer=self.position_sizer)
        df_test = self.df.copy()
        df_test["Signal"] = [0, 1, 0, 0, 0, 0, 0, 0, 0, 0]  # Buy at index 1
        report = bt.run(df_test, time_cut_period=2)

        trades_df = report["trades"]
        self.assertEqual(trades_df.iloc[0]["type"], "TIME CUT")
        self.assertEqual(
            trades_df.iloc[0]["exit_price"], 14
        )  # Close price at index 3 (1+2)

    def test_end_of_data_liquidation(self):
        bt = Backtester(initial_capital=1000, position_sizer=self.position_sizer)
        df_test = self.df.copy()
        df_test["Signal"] = [
            0,
            1,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
        ]  # Buy at index 1, no sell signal after
        report = bt.run(df_test)

        trades_df = report["trades"]
        self.assertEqual(trades_df.iloc[0]["type"], "END OF DATA")
        self.assertEqual(
            trades_df.iloc[0]["exit_price"], 20
        )  # Last close price

    def test_no_trades(self):
        bt = Backtester(initial_capital=1000, position_sizer=self.position_sizer)
        df_test = self.df.copy()
        df_test["Signal"] = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]  # No signals
        report = bt.run(df_test)

        self.assertEqual(report["summary"]["Number of Trades"], 0)
        self.assertAlmostEqual(float(report["summary"]["Final Portfolio Value"].replace("$", "").replace(",", "")), 1000)


    def test_performance_metrics(self):
        bt = Backtester(initial_capital=1000, position_sizer=self.position_sizer)
        # Simulate a scenario with drawdown
        df_test = pd.DataFrame(
            {
                "Open time": pd.to_datetime([f"2023-01-{i + 1:02d}" for i in range(5)]),
                "Open": [10, 10, 10, 10, 10],
                "High": [10, 10, 12, 10, 15],
                "Low": [10, 8, 9, 8, 10],
                "Close": [10, 8, 12, 9, 15],
                "Volume": [100, 100, 100, 100, 100],
                "Signal": [1, 0, 0, 0, -1],  # Buy at 10, Sell at 15
            }
        )
        report = bt.run(df_test)
        summary = report["summary"]

        # Buy 1000/10 = 100 units. Sell 100 * 15 = 1500
        self.assertAlmostEqual(float(summary["Final Portfolio Value"].replace('


if __name__ == "__main__":
    unittest.main()
, '').replace(',', '')), 1500)
        self.assertAlmostEqual(float(summary["Total Return (%)"]), 50.0)
        # Buy & Hold: (15/10 - 1) * 100 = 50%
        self.assertAlmostEqual(float(summary["Buy & Hold Return (%)"]), 50.0)
        # MDD: Portfolio value: 1000 -> 800 -> 1200 -> 900 -> 1500
        # Peak at 1000, drops to 800. DD = (800-1000)/1000 = -20%
        # Peak at 1200, drops to 900. DD = (900-1200)/1200 = -25%
        self.assertAlmostEqual(float(summary["Max Drawdown (MDD) (%)"]), -25.0)


if __name__ == "__main__":
    unittest.main()
, '').replace(',', '')), 1500)
        self.assertAlmostEqual(float(summary["Total Return (%)"]), 50.0)
        # Buy & Hold: (15/10 - 1) * 100 = 50%
        self.assertAlmostEqual(float(summary["Buy & Hold Return (%)"]), 50.0)
        # MDD: Portfolio value: 1000 -> 800 -> 1200 -> 900 -> 1500
        # Peak at 1000, drops to 800. DD = (800-1000)/1000 = -20%
        # Peak at 1200, drops to 900. DD = (900-1200)/1200 = -25%
        self.assertAlmostEqual(float(summary["Max Drawdown (MDD) (%)"]), -25.0)


if __name__ == "__main__":
    unittest.main()
, '').replace(',', '')), 1500)
        self.assertAlmostEqual(float(summary["Total Return (%)"]), 50.0)
        # Buy & Hold: (15/10 - 1) * 100 = 50%
        self.assertAlmostEqual(float(summary["Buy & Hold Return (%)"]), 50.0)
        # MDD: Portfolio value: 1000 -> 800 -> 1200 -> 900 -> 1500
        # Peak at 1000, drops to 800. DD = (800-1000)/1000 = -20%
        # Peak at 1200, drops to 900. DD = (900-1200)/1200 = -25%
        self.assertAlmostEqual(float(summary["Max Drawdown (MDD) (%)"]), -25.0)


if __name__ == "__main__":
    unittest.main()
