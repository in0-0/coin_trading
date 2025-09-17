"""Data provider strategies for fetching market data (e.g., klines).

This package contains the base strategy interface and concrete implementations
used by `binance_data.BinanceData` to fetch candlestick data.
"""

from .base import KlinesFetchStrategy
from .binance_klines_strategy import BinanceKlinesFetchStrategy

__all__ = [
    "KlinesFetchStrategy",
    "BinanceKlinesFetchStrategy",
]


