import os
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock

import pandas as pd

from binance_data import BinanceData, TARGET_COLUMNS


class TestBinanceData(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="bd_tests_")
        self.mock_client = MagicMock()
        self.binance_data = BinanceData("test_api_key", "test_secret_key", data_dir=self.tmpdir)
        self.binance_data.client = self.mock_client

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _sample_kline(self, opentime_ms: int, o: str, h: str, l: str, c: str, v: str):
        # 12 fields as returned by Binance
        return [
            opentime_ms,
            o,
            h,
            l,
            c,
            v,
            opentime_ms + 60_000 - 1,
            "0",
            1,
            "0",
            "0",
            "0",
        ]

    def test_initial_load_returns_standardized_columns_and_types(self):
        symbol = "BTCUSDT"
        interval = "1m"
        mock_klines = [
            self._sample_kline(1_700_000_000_000, "16000.00", "16100.00", "15900.00", "16050.00", "100.00"),
            self._sample_kline(1_700_000_060_000, "16050.00", "16200.00", "16000.00", "16150.00", "120.00"),
        ]
        self.mock_client.get_historical_klines.return_value = mock_klines

        df = self.binance_data.get_and_update_klines(symbol, interval, initial_load_days=1)

        self.assertIsInstance(df, pd.DataFrame)
        self.assertListEqual(list(df.columns), TARGET_COLUMNS)
        self.assertEqual(len(df), 2)
        self.assertTrue(pd.api.types.is_datetime64_any_dtype(df["Open time"]))
        for col in ["Open", "High", "Low", "Close", "Volume"]:
            self.assertTrue(pd.api.types.is_float_dtype(df[col]))

        # CSV should be created
        csv_path = os.path.join(self.tmpdir, f"{symbol}_{interval}.csv")
        self.assertTrue(os.path.exists(csv_path))

    def test_incremental_update_appends_new_rows_and_deduplicates(self):
        symbol = "ETHUSDT"
        interval = "1m"

        # Seed existing file with one row (simulate previous run)
        first = self._sample_kline(1_700_000_000_000, "100.0", "101.0", "99.0", "100.5", "10.0")
        self.mock_client.get_historical_klines.return_value = [first]
        df_initial = self.binance_data.get_and_update_klines(symbol, interval, initial_load_days=1)
        self.assertEqual(len(df_initial), 1)

        # Now incremental fetch from startTime = last_open_time+1
        second = self._sample_kline(1_700_000_060_000, "100.5", "102.0", "100.0", "101.5", "12.0")
        # Return duplicate first + new second to verify dedup
        self.mock_client.get_klines.return_value = [first, second]
        df_updated = self.binance_data.get_and_update_klines(symbol, interval, initial_load_days=1)

        self.assertEqual(len(df_updated), 2)
        self.assertTrue(df_updated["Open time"].is_monotonic_increasing)
        self.assertListEqual(list(df_updated.columns), TARGET_COLUMNS)


if __name__ == "__main__":
    unittest.main()
