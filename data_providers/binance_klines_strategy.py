from typing import Any, List


class BinanceKlinesFetchStrategy:
    """Default klines fetching strategy using the official Binance client.

    This class expects a `binance.client.Client`-compatible instance to be passed
    at call time. Network errors should be handled by the caller.
    """

    def fetch_initial(self, client: Any, symbol: str, interval: str, start_str: str) -> List[list]:
        return client.get_historical_klines(symbol, interval, start_str)

    def fetch_incremental(self, client: Any, symbol: str, interval: str, start_time_ms: int) -> List[list]:
        return client.get_klines(symbol=symbol, interval=interval, startTime=start_time_ms)


