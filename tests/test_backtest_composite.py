import pandas as pd

from backtests.composite_backtest import run_backtest


class StubStrategy:
    def __init__(self):
        self.slice_lengths = []

    def get_signal(self, market_data: pd.DataFrame, position):
        # record the visible slice length to verify no-lookahead
        self.slice_lengths.append(len(market_data))
        return 0  # HOLD


def test_backtester_uses_closed_candles_only_and_no_lookahead():
    n = 10
    df = pd.DataFrame({
        "Open time": pd.date_range("2024-01-01", periods=n, freq="h"),
        "Open": [100.0 + i for i in range(n)],
        "High": [101.0 + i for i in range(n)],
        "Low": [99.0 + i for i in range(n)],
        "Close": [100.5 + i for i in range(n)],
        "Volume": [100] * n,
    })
    strat = StubStrategy()
    summary = run_backtest(df=df, strategy=strat, warmup=1, fee_bps=0, slippage_bps=0)
    assert summary["iterations"] == n - 1
    # Expected slice lengths are 1..n-1 (since warmup=1 starts from index 1)
    assert strat.slice_lengths == list(range(1, n))
