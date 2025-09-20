
import pandas as pd

from trader.trade_executor import TradeExecutor


class DummyNotifier:
    def __init__(self):
        self.messages = []

    def send(self, msg: str):
        self.messages.append(msg)


class DummyStateManager:
    def __init__(self):
        self.saved = False

    def save_positions(self, positions: dict):
        self.saved = True


class DummyClient:
    pass


class DummyDataProvider:
    def __init__(self, price: float):
        self.price = price

    def get_current_price(self, symbol: str) -> float:
        return self.price

    def get_and_update_klines(self, symbol: str, interval: str) -> pd.DataFrame:
        # Provide minimal OHLCV with ATR column present
        data = {
            "Open time": pd.date_range("2024-01-01", periods=5, freq="H"),
            "Open": [self.price] * 5,
            "High": [self.price * 1.01] * 5,
            "Low": [self.price * 0.99] * 5,
            "Close": [self.price] * 5,
            "Volume": [100] * 5,
            "atr": [self.price * 0.02] * 5,
        }
        return pd.DataFrame(data)


def test_simulated_buy_sets_bracket_and_logs_composite_meta():
    symbol = "BTCUSDT"
    price = 10000.0
    positions: dict[str, object] = {}

    executor = TradeExecutor(
        client=DummyClient(),
        data_provider=DummyDataProvider(price),
        state_manager=DummyStateManager(),
        notifier=DummyNotifier(),
    )

    # New arguments to be supported by implementation
    k_sl = 1.5
    rr = 2.0
    score_meta = {"score": 0.6, "max_score": 1.0, "confidence": 0.6, "kelly_f": 0.1}

    try:
        executor.market_buy(
            symbol=symbol,
            usdt_to_spend=100.0,
            positions=positions,
            atr_multiplier=1.0,
            timeframe="5m",
            k_sl=k_sl,
            rr=rr,
            score_meta=score_meta,
        )
    except TypeError:
        # Method signature not yet updated; ensure test fails with clear message
        assert False, "market_buy must accept k_sl, rr, and score_meta keyword args"

    # Position should be created
    assert symbol in positions
    pos = positions[symbol]
    assert pos.stop_price > 0

    # A notification should contain SL and TP and composite meta
    assert executor.notifier.messages, "No notification sent"
    msg = executor.notifier.messages[-1]
    # Minimal substrings we expect after implementation
    assert "SL:" in msg, f"Expected SL in message, got: {msg}"
    assert "TP:" in msg, f"Expected TP in message, got: {msg}"
    assert ("S=" in msg) or ("Score=" in msg), f"Expected Score in message, got: {msg}"
    assert ("f*=" in msg) or ("Kelly" in msg), f"Expected Kelly fraction in message, got: {msg}"
    assert ("Conf=" in msg) or ("Confidence" in msg), f"Expected Confidence in message, got: {msg}"
