import unittest
import pandas as pd
from backtester import Backtester

class TestBacktester(unittest.TestCase):

    def setUp(self):
        # Sample DataFrame with signals for backtesting
        self.df = pd.DataFrame({
            'Open time': pd.to_datetime([f'2023-01-{i+1:02d}' for i in range(10)]),
            'Open': [10, 11, 12, 13, 14, 15, 16, 17, 18, 19],
            'High': [12, 13, 14, 15, 16, 17, 18, 19, 20, 21],
            'Low': [9, 10, 11, 12, 13, 14, 15, 16, 17, 18],
            'Close': [11, 12, 13, 14, 15, 16, 17, 18, 19, 20],
            'Volume': [100, 110, 120, 130, 140, 150, 160, 170, 180, 190],
            'Signal': [0, 1, 0, 0, 0, -1, 0, 1, 0, -1] # Buy on 2nd, Sell on 6th, Buy on 8th, Sell on 10th
        })

    def test_initialization(self):
        bt = Backtester(initial_capital=5000)
        self.assertEqual(bt.initial_capital, 5000)
        self.assertEqual(bt.cash, 5000)
        self.assertEqual(bt.position_size, 0)
        self.assertEqual(len(bt.trades), 0)

    def test_buy_and_sell_signals(self):
        bt = Backtester(initial_capital=1000)
        df_test = self.df.copy()
        df_test['Signal'] = [0, 1, 0, 0, 0, -1, 0, 0, 0, 0] # Simple buy then sell
        bt.run(df_test)

        self.assertGreater(len(bt.trades), 0)
        self.assertEqual(bt.trades[0]['type'], 'BUY')
        self.assertEqual(bt.trades[0]['price'], 12) # Close price at index 1
        self.assertEqual(bt.trades[1]['type'], 'SELL SIGNAL')
        self.assertEqual(bt.trades[1]['price'], 16) # Close price at index 5
        
        # Check final value after a simple trade
        # Buy 1000/12 = 83.33 units. Sell 83.33 * 16 = 1333.33
        self.assertAlmostEqual(bt.final_value, 1333.3333333333333)
        self.assertAlmostEqual(bt.total_return, 33.33333333333333)

    def test_take_profit(self):
        bt = Backtester(initial_capital=1000, take_profit_pct=0.10) # 10% TP
        df_test = self.df.copy()
        df_test['Signal'] = [0, 1, 0, 0, 0, 0, 0, 0, 0, 0] # Only buy signal
        # Manually adjust prices to trigger TP
        df_test.loc[2, 'High'] = df_test.loc[1, 'Close'] * 1.11 # Trigger TP at index 2
        bt.run(df_test)

        self.assertEqual(bt.trades[0]['type'], 'BUY')
        self.assertEqual(bt.trades[1]['type'], 'TAKE PROFIT')
        self.assertAlmostEqual(bt.trades[1]['price'], 12 * 1.10) # 12 (entry) * 1.10

    def test_stop_loss(self):
        bt = Backtester(initial_capital=1000, stop_loss_pct=0.05) # 5% SL
        df_test = self.df.copy()
        df_test['Signal'] = [0, 1, 0, 0, 0, 0, 0, 0, 0, 0] # Only buy signal
        # Manually adjust prices to trigger SL
        df_test.loc[2, 'Low'] = df_test.loc[1, 'Close'] * 0.94 # Trigger SL at index 2
        bt.run(df_test)

        self.assertEqual(bt.trades[0]['type'], 'BUY')
        self.assertEqual(bt.trades[1]['type'], 'STOP LOSS')
        self.assertAlmostEqual(bt.trades[1]['price'], 12 * 0.95) # 12 (entry) * 0.95

    def test_time_cut(self):
        bt = Backtester(initial_capital=1000, exit_params={"time_cut_period": 2})
        df_test = self.df.copy()
        df_test['Signal'] = [0, 1, 0, 0, 0, 0, 0, 0, 0, 0] # Buy at index 1
        bt.run(df_test)

        self.assertEqual(bt.trades[0]['type'], 'BUY')
        self.assertEqual(bt.trades[1]['type'], 'TIME CUT')
        self.assertEqual(bt.trades[1]['price'], 14) # Close price at index 3 (1+2)

    def test_end_of_data_liquidation(self):
        bt = Backtester(initial_capital=1000)
        df_test = self.df.copy()
        df_test['Signal'] = [0, 1, 0, 0, 0, 0, 0, 0, 0, 0] # Buy at index 1, no sell signal after
        bt.run(df_test)

        self.assertEqual(bt.trades[0]['type'], 'BUY')
        self.assertEqual(bt.trades[1]['type'], 'END OF DATA')
        self.assertEqual(bt.trades[1]['price'], 20) # Last close price

    def test_no_trades(self):
        bt = Backtester(initial_capital=1000)
        df_test = self.df.copy()
        df_test['Signal'] = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0] # No signals
        bt.run(df_test)

        self.assertEqual(len(bt.trades), 0)
        self.assertEqual(bt.final_value, 1000)
        self.assertEqual(bt.total_return, 0)

    def test_performance_metrics(self):
        bt = Backtester(initial_capital=1000)
        # Simulate a scenario with drawdown
        df_test = pd.DataFrame({
            'Open time': pd.to_datetime([f'2023-01-{i+1:02d}' for i in range(5)]),
            'Open': [10, 10, 10, 10, 10],
            'High': [10, 10, 10, 10, 10],
            'Low': [10, 10, 10, 10, 10],
            'Close': [10, 8, 12, 9, 15],
            'Volume': [100, 100, 100, 100, 100],
            'Signal': [0, 1, 0, 0, -1] # Buy at 8, Sell at 15
        })
        bt.run(df_test)
        
        # Buy 1000/8 = 125 units. Sell 125 * 15 = 1875
        self.assertAlmostEqual(bt.final_value, 1875)
        self.assertAlmostEqual(bt.total_return, 87.5)
        # Buy & Hold: (15/10 - 1) * 100 = 50%
        self.assertAlmostEqual(bt.buy_and_hold_return, 50.0)
        # MDD: Portfolio value goes from 1000 -> 125*8=1000 -> 125*12=1500 -> 125*9=1125 -> 125*15=1875
        # Peak at 1500, then drops to 1125. Drawdown = (1125-1500)/1500 = -0.25 = -25%
        self.assertAlmostEqual(bt.max_drawdown, -25.0)

if __name__ == '__main__':
    unittest.main()
