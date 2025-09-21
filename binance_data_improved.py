"""
개선된 Binance 데이터 제공자

Pydantic 모델을 활용한 강력한 데이터 검증과 타입 안정성을 제공합니다.
"""

import logging
import time
import os
from datetime import datetime, timedelta
from typing import Final, List, Optional, Dict, Any, cast

import pandas as pd
from binance.client import Client
from binance.exceptions import BinanceAPIException

from data_providers.base import KlinesFetchStrategy
from data_providers.binance_klines_strategy import BinanceKlinesFetchStrategy
from core.data_models import KlineData, NormalizedKlineData, MarketDataSummary, validate_kline_data
from core.exceptions import DataError, NetworkError, ValidationError
from core.error_handler import ErrorHandler

# 컬럼 이름을 상수로 정의하여 오타 방지 및 가독성 향상
KLINE_COLUMNS: Final[List[str]] = [
    "Open time", "Open", "High", "Low", "Close", "Volume", "Close time",
    "Quote asset volume", "Number of trades", "Taker buy base asset volume",
    "Taker buy quote asset volume", "Ignore"
]
TARGET_COLUMNS: Final[List[str]] = ["Open time", "Open", "High", "Low", "Close", "Volume"]
NUMERIC_COLUMNS: Final[List[str]] = ["Open", "High", "Low", "Close", "Volume"]


class ImprovedBinanceData:
    """
    개선된 Binance 데이터 제공자

    주요 개선사항:
    - Pydantic 모델을 활용한 강력한 데이터 검증
    - 통일된 에러 처리
    - 타입 안정성 보장
    - 데이터 무결성 검증
    """

    def __init__(
        self,
        api_key: str,
        secret_key: str,
        data_dir: str = "data/",
        fetch_strategy: Optional[KlinesFetchStrategy] = None,
        error_handler: Optional[ErrorHandler] = None
    ):
        """
        Args:
            api_key: Binance API 키
            secret_key: Binance 시크릿 키
            data_dir: 데이터 저장 디렉토리
            fetch_strategy: Kline 데이터 조회 전략
            error_handler: 에러 처리 핸들러
        """
        self.client = Client(api_key, secret_key)
        self.data_dir = data_dir
        self.fetch_strategy = fetch_strategy or BinanceKlinesFetchStrategy()
        self.error_handler = error_handler or ErrorHandler()
        self.logger = logging.getLogger(__name__)

        os.makedirs(self.data_dir, exist_ok=True)

    def get_and_update_klines(
        self,
        symbol: str,
        interval: str,
        initial_load_days: int = 30
    ) -> pd.DataFrame:
        """
        Kline 데이터를 조회하고 업데이트하며 검증된 DataFrame 반환

        Args:
            symbol: 심볼 (예: 'BTCUSDT')
            interval: 시간 간격 (예: '5m', '1h')
            initial_load_days: 초기 로드 일수

        Returns:
            검증된 Kline 데이터 DataFrame

        Raises:
            DataError: 데이터 처리 중 오류 발생 시
        """
        with self.error_handler.create_safe_context(log_level="warning", notify=False):
            return self._get_and_update_klines_safe(symbol, interval, initial_load_days)

    def _get_and_update_klines_safe(
        self,
        symbol: str,
        interval: str,
        initial_load_days: int = 30
    ) -> pd.DataFrame:
        """안전한 Kline 데이터 조회 및 업데이트"""
        file_path = os.path.join(self.data_dir, f"{symbol}_{interval}.csv")

        # 기존 데이터 로드
        df_existing = self._load_existing_data(file_path)

        # 시작 타임스탬프 계산
        start_timestamp = self._get_start_timestamp(df_existing)

        # 새로운 데이터 조회
        try:
            if start_timestamp is None:
                # 초기 데이터 로드
                start_str = (datetime.utcnow() - timedelta(days=initial_load_days)).strftime("%Y-%m-%d %H:%M:%S")
                raw_klines = self.fetch_strategy.fetch_initial(self.client, symbol, interval, start_str)
            else:
                # 증분 데이터 로드
                raw_klines = self.fetch_strategy.fetch_incremental(self.client, symbol, interval, start_timestamp)

            if not raw_klines:
                self.logger.warning(f"No new klines returned for {symbol} {interval}")
                return self._ensure_dataframe_columns(df_existing)

            # 데이터 검증 및 변환
            validated_klines = self._validate_and_normalize_klines(raw_klines, symbol)

            # DataFrame 생성 및 병합 (UTC-naive로 표준화)
            df_new = pd.DataFrame(validated_klines)
            if "Open time" in df_new.columns:
                try:
                    df_new["Open time"] = pd.to_datetime(df_new["Open time"], utc=True).dt.tz_localize(None)
                except Exception:
                    # 실패 시 기본 변환 시도
                    df_new["Open time"] = pd.to_datetime(df_new["Open time"], errors="coerce")
            df_combined = self._combine_dataframes(df_existing, df_new)

            # 파일 저장
            df_combined.to_csv(file_path, index=False)

            return df_combined

        except BinanceAPIException as e:
            error_context = {
                "symbol": symbol,
                "interval": interval,
                "operation": "fetch_klines"
            }
            raise NetworkError(
                f"Failed to fetch klines: {e}",
                endpoint=f"klines/{symbol}/{interval}",
                context=error_context
            ) from e
        except Exception as e:
            error_context = {
                "symbol": symbol,
                "interval": interval,
                "operation": "process_klines"
            }
            raise DataError(
                f"Failed to process klines: {e}",
                symbol=symbol,
                timeframe=interval,
                context=error_context
            ) from e

    def _validate_and_normalize_klines(self, raw_klines: List[List], symbol: str) -> List[Dict[str, Any]]:
        """Kline 데이터 검증 및 정규화"""
        try:
            # 열린 캔들 제거: close time(ms)가 현재 시각보다 미래인 행 제외
            try:
                now_ms = int(time.time() * 1000)
                raw_klines = [row for row in raw_klines if len(row) > 6 and int(row[6]) <= now_ms]
            except Exception:
                # 필터링 실패 시 원본 그대로 진행 (검증에서 걸러짐)
                pass

            # Pydantic 모델을 사용한 검증
            validated_data = validate_kline_data(raw_klines)

            # 딕셔너리 형태로 변환
            return [
                {
                    "Open time": kline.open_time,
                    "Open": kline.open,
                    "High": kline.high,
                    "Low": kline.low,
                    "Close": kline.close,
                    "Volume": kline.volume
                }
                for kline in validated_data
            ]

        except ValidationError as e:
            error_context = {
                "symbol": symbol,
                "raw_data_length": len(raw_klines),
                "validation_error": str(e)
            }
            raise DataError(
                f"Kline data validation failed: {e}",
                symbol=symbol,
                context=error_context
            ) from e

    def _load_existing_data(self, file_path: str) -> Optional[pd.DataFrame]:
        """기존 데이터 파일 로드"""
        if not os.path.exists(file_path):
            return None

        try:
            df = pd.read_csv(file_path)

            # 컬럼명 정규화
            if "Open time" in df.columns:
                df["Open time"] = pd.to_datetime(df["Open time"], errors="coerce")
            elif "open time" in df.columns:
                df.rename(columns={"open time": "Open time"}, inplace=True)
                df["Open time"] = pd.to_datetime(df["Open time"], errors="coerce")

            # 숫자형 컬럼 변환
            for col in NUMERIC_COLUMNS:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")

            # NaN 값 제거
            df = df.dropna()

            return df

        except (pd.errors.EmptyDataError, FileNotFoundError, ValueError) as e:
            self.logger.warning(f"Existing data not loaded from {file_path}: {e}")
            return None

    def _get_start_timestamp(self, df: Optional[pd.DataFrame]) -> Optional[int]:
        """다음 조회를 위한 시작 타임스탬프 계산"""
        if df is None or df.empty:
            return None

        try:
            last_open_time = df["Open time"].dropna().iloc[-1]
            if not pd.api.types.is_datetime64_any_dtype(pd.Series([last_open_time])):
                last_open_time = pd.to_datetime(last_open_time)

            return int(last_open_time.timestamp() * 1000) + 1

        except Exception as e:
            self.logger.warning(f"Failed to calculate start timestamp: {e}")
            return None

    def _combine_dataframes(self, df_existing: Optional[pd.DataFrame], df_new: pd.DataFrame) -> pd.DataFrame:
        """기존 데이터와 새 데이터를 결합"""
        if df_existing is not None:
            # 중복 제거 및 정렬
            df_combined = pd.concat([df_existing, df_new], ignore_index=True)
            df_combined.drop_duplicates(subset="Open time", keep="last", inplace=True)
        else:
            df_combined = df_new

        # 정렬 전에 타임존 표준화 (모두 naive)
        try:
            if "Open time" in df_combined.columns:
                df_combined["Open time"] = pd.to_datetime(df_combined["Open time"], utc=True).dt.tz_localize(None)
        except Exception:
            pass
        df_combined.sort_values(by="Open time", inplace=True)
        return df_combined

    def _ensure_dataframe_columns(self, df: Optional[pd.DataFrame]) -> pd.DataFrame:
        """DataFrame이 TARGET_COLUMNS를 포함하도록 보장"""
        if df is not None:
            # Ensure DataFrame slice and type for static checkers
            return cast(pd.DataFrame, df.loc[:, TARGET_COLUMNS].copy())
        else:
            return pd.DataFrame(columns=pd.Index(TARGET_COLUMNS))

    def get_current_price(self, symbol: str) -> float:
        """
        현재가 조회

        Args:
            symbol: 심볼

        Returns:
            현재가

        Raises:
            DataError: 가격 조회 실패 시
        """
        with self.error_handler.create_safe_context(log_level="warning", notify=False):
            return self._get_current_price_safe(symbol)

    def _get_current_price_safe(self, symbol: str) -> float:
        """안전한 현재가 조회"""
        try:
            ticker = self.client.get_symbol_ticker(symbol=symbol)
            price = float(ticker["price"])

            if price <= 0:
                raise DataError(
                    f"Invalid price for {symbol}: {price}",
                    symbol=symbol
                )

            return price

        except BinanceAPIException as e:
            raise NetworkError(
                f"Failed to fetch current price for {symbol}: {e}",
                endpoint=f"ticker/price/{symbol}",
                context={"symbol": symbol}
            ) from e
        except (ValueError, KeyError) as e:
            raise DataError(
                f"Invalid price data for {symbol}: {e}",
                symbol=symbol,
                context={"ticker": str(e)}
            ) from e

    def get_market_summary(self, symbol: str, interval: str) -> MarketDataSummary:
        """
        시장 데이터 요약 정보 반환

        Args:
            symbol: 심볼
            interval: 시간 간격

        Returns:
            시장 데이터 요약
        """
        with self.error_handler.create_safe_context(log_level="warning", notify=False):
            return self._get_market_summary_safe(symbol, interval)

    def _get_market_summary_safe(self, symbol: str, interval: str) -> MarketDataSummary:
        """안전한 시장 데이터 요약 조회"""
        file_path = os.path.join(self.data_dir, f"{symbol}_{interval}.csv")
        df = self._load_existing_data(file_path)

        if df is None or df.empty:
            raise DataError(
                f"No market data available for {symbol} {interval}",
                symbol=symbol,
                timeframe=interval
            )

        latest_price = self.get_current_price(symbol)

        start_dt = pd.to_datetime(df["Open time"].min()).to_pydatetime()
        end_dt = pd.to_datetime(df["Open time"].max()).to_pydatetime()

        return MarketDataSummary(
            symbol=symbol,
            timeframe=interval,
            data_points=len(df),
            start_time=start_dt,
            end_time=end_dt,
            latest_price=latest_price,
            volume_24h=self._calculate_24h_volume(df)
        )

    def _calculate_24h_volume(self, df: pd.DataFrame) -> Optional[float]:
        """24시간 거래량 계산"""
        try:
            # 최근 24시간 데이터 필터링 (대략적인 계산)
            cutoff_time = datetime.utcnow() - timedelta(hours=24)
            recent_data = df[df["Open time"] >= cutoff_time]

            if not recent_data.empty:
                return float(recent_data["Volume"].sum())
            return None

        except Exception as e:
            self.logger.warning(f"Failed to calculate 24h volume: {e}")
            return None

    def validate_data_integrity(self, symbol: str, interval: str) -> List[str]:
        """
        데이터 무결성 검증

        Args:
            symbol: 심볼
            interval: 시간 간격

        Returns:
            검증 오류 메시지 리스트
        """
        errors = []

        try:
            file_path = os.path.join(self.data_dir, f"{symbol}_{interval}.csv")
            df = self._load_existing_data(file_path)

            if df is None:
                errors.append("No data file found")
                return errors

            # 기본 검증
            if df.empty:
                errors.append("Data file is empty")
                return errors

            # 시간 순서 검증
            if not df["Open time"].is_monotonic_increasing:
                errors.append("Timestamps are not in ascending order")

            # 가격 논리 검증
            for col in NUMERIC_COLUMNS:
                if (df[col] <= 0).any():
                    errors.append(f"Invalid {col} values found (must be > 0)")

            # 가격 일관성 검증
            if (df["High"] < df["Low"]).any():
                errors.append("High price is lower than low price in some records")

            if (df["Open"] > df["High"]).any():
                errors.append("Open price is higher than high price in some records")

            if (df["Close"] > df["High"]).any():
                errors.append("Close price is higher than high price in some records")

        except Exception as e:
            errors.append(f"Data integrity check failed: {e}")

        return errors
