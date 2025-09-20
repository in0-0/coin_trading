from types import SimpleNamespace

import numpy as np
import pandas as pd


def make_df(n=120, start=100.0, drift=0.2, vol=1.0):
    rng = np.random.default_rng(42)
    close = start + np.cumsum(rng.normal(drift, vol, size=n))
    high = close + np.abs(rng.normal(0.2, 0.1, size=n))
    low = close - np.abs(rng.normal(0.2, 0.1, size=n))
    open_ = np.r_[close[0], close[:-1]]
    volu = rng.integers(100, 1000, size=n)
    df = pd.DataFrame({
        "Open": open_,
        "High": high,
        "Low": low,
        "Close": close,
        "Volume": volu.astype(float),
    })
    return df


def test_composite_strategy_score_and_signal_interfaces():
    from models import Signal
    from strategies.composite_signal_strategy import CompositeSignalStrategy

    cfg = SimpleNamespace(
        ema_fast=12,
        ema_slow=26,
        bb_len=20,
        rsi_len=14,
        macd_fast=12,
        macd_slow=26,
        macd_signal=9,
        atr_len=14,
        k_atr_norm=1.0,
        vol_len=20,
        obv_span=20,
        max_score=1.0,
        buy_threshold=0.0,
        sell_threshold=-0.5,
        weights=SimpleNamespace(ma=0.3, bb=0.15, rsi=0.15, macd=0.25, vol=0.1, obv=0.05),
    )

    df = make_df()
    strat = CompositeSignalStrategy(config=cfg)

    s = strat.score(df)
    assert isinstance(s, float)
    assert -1.0 <= s <= 1.0

    sig = strat.get_signal(df, position=None)
    assert isinstance(sig, Signal)


