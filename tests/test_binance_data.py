import unittest
from unittest.mock import MagicMock, patch
import pandas as pd
from binance.client import Client
from binance_data import BinanceData

class TestBinanceData(unittest.TestCase):

    def setUp(self):
        self.mock_client = MagicMock()
        self.binance_data = BinanceData("test_api_key", "test_secret_key")
        self.binance_data.client = self.mock_client

    def test_get_historical_data(self):
        # Mocking klines data from Binance API
        mock_klines = [
            [1672531200000, "16000.00", "16100.00", "15900.00", "16050.00", "100.00", 1672617599999, "1605000.00", 1000, "50.00", "800000.00", "0"],
            [1672617600000, "16050.00", "16200.00", "16000.00", "16150.00", "120.00", 1672703999999, "1938000.00", 1200, "60.00", "960000.00", "0"],
        ]
        self.mock_client.get_historical_klines.return_value = mock_klines

        df = self.binance_data.get_historical_data('BTCUSDT', Client.KLINE_INTERVAL_1DAY, '1 Jan, 2023')

        self.assertIsInstance(df, pd.DataFrame)
        self.assertFalse(df.empty)
        self.assertEqual(len(df), 2)
        self.assertListEqual(list(df.columns), ['Open time', 'Open', 'High', 'Low', 'Close', 'Volume'])
        self.assertEqual(df['Open time'].dtype, 'datetime64[ns]')
        self.assertEqual(df['Open'].dtype, float)
        self.assertEqual(df['Close'].dtype, float)

    def test_add_moving_average(self):
        data = {
            'Open time': pd.to_datetime(['2023-01-01', '2023-01-02', '2023-01-03', '2023-01-04', '2023-01-05']),
            'Open': [10, 11, 12, 13, 14],
            'High': [12, 13, 14, 15, 16],
            'Low': [9, 10, 11, 12, 13],
            'Close': [10, 11, 12, 13, 14],
            'Volume': [100, 110, 120, 130, 140]
        }
        df = pd.DataFrame(data)

        df_ma = self.binance_data.add_moving_average(df.copy(), 3)

        self.assertIn('MA_3', df_ma.columns)
        self.assertTrue(pd.isna(df_ma['MA_3'].iloc[0]))
        self.assertTrue(pd.isna(df_ma['MA_3'].iloc[1]))
        self.assertAlmostEqual(df_ma['MA_3'].iloc[2], (10+11+12)/3)
        self.assertAlmostEqual(df_ma['MA_3'].iloc[3], (11+12+13)/3)
        self.assertAlmostEqual(df_ma['MA_3'].iloc[4], (12+13+14)/3)

if __name__ == '__main__':
    unittest.main()
