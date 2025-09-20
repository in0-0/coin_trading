import os
import json
import tempfile
import pandas as pd

from backtests.composite_backtest import run_backtest


class AlwaysTradeStrategy:
    def __init__(self):
        self.toggle = False

    def get_signal(self, df, position=None):
        # alternate to simulate entries/exits in a naive way within the stub loop
        self.toggle = not self.toggle
        return None


def test_backtest_summary_contains_kelly_inputs_and_metrics_keys():
    df = pd.DataFrame({
        "Open time": pd.date_range("2025-01-01", periods=20, freq="T"),
        "Open": [100.0] * 20,
        "High": [101.0] * 20,
        "Low": [99.0] * 20,
        "Close": [100.0] * 20,
        "Volume": [1.0] * 20,
    })
    with tempfile.TemporaryDirectory() as tmpdir:
        summary = run_backtest(df=df, strategy=AlwaysTradeStrategy(), warmup=2, fee_bps=0, slippage_bps=0, write_logs=True, log_dir=tmpdir, run_id="bt_metrics")
        base = os.path.join(tmpdir, "bt_metrics")
        path = os.path.join(base, "summary.json")
        assert os.path.exists(path)
        with open(path, "r") as f:
            data = json.load(f)
        # keys expected after implementation
        for key in [
            "iterations", "trades", "pnl",
            "win_rate_p", "avg_win", "avg_loss", "payoff_b", "expectancy",
            "kelly_inputs",
        ]:
            assert key in data


