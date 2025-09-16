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
        """
        Fetch klines incrementally and persist to CSV. Always return Title-cased TARGET_COLUMNS
        with correct dtypes: "Open time" as datetime64[ns], numeric columns as float.
        """
        file_path = os.path.join(self.data_dir, f"{symbol}_{interval}.csv")

        df_existing = self._load_existing_data(file_path)
        start_timestamp = self._get_start_timestamp(df_existing)

        try:
            if start_timestamp is None:
                start_str = (datetime.utcnow() - timedelta(days=initial_load_days)).strftime("%Y-%m-%d %H:%M:%S")
                klines = self.client.get_historical_klines(symbol, interval, start_str)
            else:
                klines = self.client.get_klines(symbol=symbol, interval=interval, startTime=start_timestamp)
        except BinanceAPIException as e:
            logging.error(f"Failed to fetch klines for {symbol} {interval}: {e}")
            return df_existing[TARGET_COLUMNS] if df_existing is not None else pd.DataFrame(columns=TARGET_COLUMNS)

        if not klines:
            logging.warning(f"No new klines returned for {symbol} {interval}.")
            return df_existing[TARGET_COLUMNS] if df_existing is not None else pd.DataFrame(columns=TARGET_COLUMNS)

        df_new = pd.DataFrame(klines, columns=KLINE_COLUMNS)
        # Normalize types
        df_new["Open time"] = pd.to_datetime(df_new["Open time"], unit="ms", errors="coerce")
        for col in NUMERIC_COLUMNS:
            df_new[col] = pd.to_numeric(df_new[col], errors="coerce")

        df_combined = pd.concat([df_existing, df_new], ignore_index=True) if df_existing is not None else df_new

        df_combined.drop_duplicates(subset="Open time", keep="last", inplace=True)
        df_combined.sort_values(by="Open time", inplace=True)

        # Ensure final dtypes
        for col in NUMERIC_COLUMNS:
            df_combined[col] = pd.to_numeric(df_combined[col], errors='coerce')

        # Persist full set for durability
        df_combined.to_csv(file_path, index=False)

        # Return standardized view
        return df_combined[TARGET_COLUMNS]

    def _load_existing_data(self, file_path):
        if not os.path.exists(file_path):
            return None
        try:
            df = pd.read_csv(file_path)
            # Fix prior case typo and ensure correct dtype
            if "Open time" in df.columns:
                df["Open time"] = pd.to_datetime(df["Open time"], errors="coerce")
            elif "open time" in df.columns:
                # Migrate legacy column to Title case
                df.rename(columns={"open time": "Open time"}, inplace=True)
                df["Open time"] = pd.to_datetime(df["Open time"], errors="coerce")

            # Ensure numeric dtypes for core columns if present
            for col in NUMERIC_COLUMNS:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            return df
        except (pd.errors.EmptyDataError, FileNotFoundError) as e:
            logging.warning(f"Existing data not loaded from {file_path}: {e}")
            return None

    def _get_start_timestamp(self, df):
        if df is None or df.empty:
            return None
        last_open_time = df["Open time"].dropna().iloc[-1]
        # If dtype not datetime (corrupted), coerce
        if not pd.api.types.is_datetime64_any_dtype(pd.Series([last_open_time])):
            try:
                last_open_time = pd.to_datetime(last_open_time)
            except Exception:
                return None
        return int(last_open_time.timestamp() * 1000) + 1

    def get_current_price(self, symbol: str) -> float:
        try:
            ticker = self.client.get_symbol_ticker(symbol=symbol)
            return float(ticker["price"])
        except BinanceAPIException as e:
            logging.error(f"Error fetching current price for {symbol}: {e}")
            return 0.0
