import os
import logging
import pandas as pd
from binance.client import Client
from binance.exceptions import BinanceAPIException
from datetime import datetime, timedelta

# 컬럼 이름을 상수로 정의하여 오타 방지 및 가독성 향상
KLINE_COLUMNS = [
    "Open time", "Open", "High", "Low", "Close", "Volume", "Close time",
    "Quote asset volume", "Number of trades", "Taker buy base asset volume",
    "Taker buy quote asset volume", "Ignore"
]
TARGET_COLUMNS = ["Open time", "Open", "High", "Low", "Close", "Volume"]
NUMERIC_COLUMNS = ["Open", "High", "Low", "Close", "Volume"]

class BinanceData:
    def __init__(self, api_key, secret_key, data_dir="data/"):
        self.client = Client(api_key, secret_key)
        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)

    def get_and_update_klines(self, symbol, interval, initial_load_days=30):
        file_path = os.path.join(self.data_dir, f"{symbol}_{interval}.csv")
        
        df_existing = self._load_existing_data(file_path)
        start_timestamp = self._get_start_timestamp(df_existing)

        if start_timestamp is None:
            start_str = (datetime.utcnow() - timedelta(days=initial_load_days)).strftime("%Y-%m-%d %H:%M:%S")
            klines = self.client.get_historical_klines(symbol, interval, start_str)
        else:
            klines = self.client.get_klines(symbol=symbol, interval=interval, startTime=start_timestamp)

        if not klines:
            return df_existing[TARGET_COLUMNS] if df_existing is not None else pd.DataFrame(columns=TARGET_COLUMNS)

        df_new = pd.DataFrame(klines, columns=KLINE_COLUMNS)
        df_new["Open time"] = pd.to_datetime(df_new["Open time"], unit="ms")

        df_combined = pd.concat([df_existing, df_new], ignore_index=True) if df_existing is not None else df_new
        
        df_combined.drop_duplicates(subset="Open time", keep="last", inplace=True)
        df_combined.sort_values(by="Open time", inplace=True)
        
        for col in NUMERIC_COLUMNS:
            df_combined[col] = pd.to_numeric(df_combined[col], errors='coerce')

        df_combined.to_csv(file_path, index=False)

        return df_combined[TARGET_COLUMNS]

    def _load_existing_data(self, file_path):
        if not os.path.exists(file_path):
            return None
        try:
            df = pd.read_csv(file_path)
            df["open time"] = pd.to_datetime(df["Open time"])
            return df
        except (pd.errors.EmptyDataError, FileNotFoundError):
            return None

    def _get_start_timestamp(self, df):
        if df is None or df.empty:
            return None
        return int(df["Open time"].iloc[-1].timestamp() * 1000) + 1

    def get_current_price(self, symbol: str) -> float:
        try:
            ticker = self.client.get_symbol_ticker(symbol=symbol)
            return float(ticker["price"])
        except BinanceAPIException as e:
            logging.error(f"Error fetching current price for {symbol}: {e}")
            return 0.0
