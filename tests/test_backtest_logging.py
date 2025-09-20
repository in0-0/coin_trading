import os
import tempfile

import pandas as pd

from backtests.composite_backtest import run_backtest


class StubStrategy:
    def get_signal(self, df, position=None):
        return None


def test_backtest_writes_summary_and_series_when_enabled():
    df = pd.DataFrame({
        "Open time": pd.date_range("2025-01-01", periods=10, freq="T"),
        "Open": [100.0] * 10,
        "High": [101.0] * 10,
        "Low": [99.0] * 10,
        "Close": [100.0] * 10,
        "Volume": [1.0] * 10,
    })
    with tempfile.TemporaryDirectory() as tmpdir:
        summary = run_backtest(df=df, strategy=StubStrategy(), warmup=1, fee_bps=0, slippage_bps=0, write_logs=True, log_dir=tmpdir, run_id="bt1")
        base = os.path.join(tmpdir, "bt1")
        assert os.path.exists(os.path.join(base, "summary.json"))
        assert os.path.exists(os.path.join(base, "equity.csv"))
        assert os.path.exists(os.path.join(base, "trades.csv"))
