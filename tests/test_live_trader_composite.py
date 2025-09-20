from unittest import mock


def test_live_trader_uses_composite_and_kelly_sizing(monkeypatch):
    # Ensure composite strategy path is taken
    monkeypatch.setenv("STRATEGY_NAME", "composite_signal")

    import live_trader_gpt as lt
    # Ensure runtime switch even if module was imported earlier by other tests
    lt.STRATEGY_NAME = "composite_signal"

    # Mock BinanceData to return simple increasing candles
    import pandas as pd
    df = pd.DataFrame({
        "Open": [100, 101, 102, 103, 104, 105, 106, 107, 108, 109],
        "High": [101, 102, 103, 104, 105, 106, 107, 108, 109, 110],
        "Low": [99, 100, 101, 102, 103, 104, 105, 106, 107, 108],
        "Close": [101, 102, 103, 104, 105, 106, 107, 108, 109, 110],
        "Volume": [1000.0] * 10,
    })

    class DummyData:
        def __init__(self, *args, **kwargs):
            pass
        def get_and_update_klines(self, symbol, interval):
            return df.copy()
        def get_current_price(self, symbol):
            return float(df["Close"].iloc[-1])

    class DummyExec:
        def __init__(self, *args, **kwargs):
            self._balance = 1000.0
            self.execution_mode = "SIMULATED"
        def get_usdt_balance(self):
            return self._balance
        def market_buy(self, symbol, usdt_to_spend, positions, atr_multiplier, timeframe):
            # If Kelly sizing worked, spend should be > MIN_ORDER_USDT
            assert usdt_to_spend > 10.0
            positions[symbol] = mock.Mock()
        def market_sell(self, symbol, positions):
            positions.pop(symbol, None)

    with mock.patch.object(lt, 'BinanceData', DummyData), \
         mock.patch.object(lt, 'TradeExecutor', DummyExec), \
         mock.patch.object(lt, 'Notifier'):
        trader = lt.LiveTrader()
        # Limit to a single symbol to exercise the flow deterministically
        lt.SYMBOLS[:] = lt.SYMBOLS[:1]
        trader._find_and_execute_entries()


