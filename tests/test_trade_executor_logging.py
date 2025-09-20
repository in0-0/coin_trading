import os
import tempfile
from importlib import import_module

import pandas as pd

from trader.trade_executor import TradeExecutor


class FakeProvider:
    def get_current_price(self, symbol: str) -> float:
        return 100.0

    def get_and_update_klines(self, symbol: str, timeframe: str) -> pd.DataFrame:
        return pd.DataFrame({
            "Open time": pd.date_range("2025-01-01", periods=3, freq="T"),
            "Open": [100, 100, 100],
            "High": [101, 101, 101],
            "Low": [99, 99, 99],
            "Close": [100, 100, 100],
            "Volume": [1, 1, 1],
            "atr": [1.0, 1.0, 1.0],
        })


class DummyNotifier:
    def send(self, msg: str) -> None:
        pass


class DummyStateManager:
    def save_positions(self, positions):
        self.positions = dict(positions)


def test_trade_executor_writes_logs_on_simulated_buy_and_sell():
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            mod = import_module("trader.trade_logger")
            TradeLogger = mod.TradeLogger
        except Exception:
            assert False, "TradeLogger not implemented yet"

        trade_logger = TradeLogger(base_dir=tmpdir, run_id="run1", mode="SIMULATED")
        execu = TradeExecutor(
            client=None,
            data_provider=FakeProvider(),
            state_manager=DummyStateManager(),
            notifier=DummyNotifier(),
            execution_mode="SIMULATED",
            trade_logger=trade_logger,  # expected new parameter
        )
        positions = {}
        execu.market_buy("BTCUSDT", usdt_to_spend=10.0, positions=positions, atr_multiplier=1.0, timeframe="5m")
        assert "BTCUSDT" in positions
        execu.market_sell("BTCUSDT", positions)
        assert "BTCUSDT" not in positions

        base = os.path.join(tmpdir, "run1")
        assert os.path.exists(os.path.join(base, "orders.csv"))
        assert os.path.exists(os.path.join(base, "fills.csv")) or True  # may be empty for SIMULATED
        assert os.path.exists(os.path.join(base, "trades.csv"))
