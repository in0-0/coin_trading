from typing import Protocol, Any, List


class KlinesFetchStrategy(Protocol):
    """Strategy interface for fetching klines.

    Implementations should wrap a specific client API. The returned klines
    must be a list of rows compatible with `binance_data.KLINE_COLUMNS`.
    """

    def fetch_initial(self, client: Any, symbol: str, interval: str, start_str: str) -> List[list]:
        """Fetch initial historical klines starting from a datetime string.

        Parameters
        ----------
        client: Any
            An API client compatible with the expected methods (e.g., Binance Client).
        symbol: str
            Trading symbol, e.g., "BTCUSDT".
        interval: str
            Kline interval, e.g., "1m".
        start_str: str
            Start datetime string accepted by the underlying provider.
        """
        ...

    def fetch_incremental(self, client: Any, symbol: str, interval: str, start_time_ms: int) -> List[list]:
        """Fetch incremental klines starting from a millisecond timestamp.

        Parameters are similar to `fetch_initial`, but use a millisecond timestamp
        to avoid re-downloading candles already persisted.
        """
        ...


