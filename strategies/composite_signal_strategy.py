
import numpy as np
import pandas as pd
import pandas_ta as ta

from models import Position, Signal
from strategies.base_strategy import Strategy


class CompositeSignalStrategy(Strategy):
    def __init__(self, config):
        self.cfg = config

    def _features(self, df: pd.DataFrame) -> pd.DataFrame:
        x = df.copy()
        # Indicators
        n = len(x)
        ema_fast_len = min(int(getattr(self.cfg, "ema_fast", 12)), max(2, n))
        ema_slow_len = min(int(getattr(self.cfg, "ema_slow", 26)), max(2, n))
        x["ema_fast"] = ta.ema(x["Close"], length=ema_fast_len)
        x["ema_slow"] = ta.ema(x["Close"], length=ema_slow_len)

        bb_len = min(int(getattr(self.cfg, "bb_len", 20)), max(5, n))
        bb = ta.bbands(x["Close"], length=bb_len)
        if bb is not None and bb.shape[1] >= 3:
            # pandas_ta names: BBM_len_mult, BBU_len_mult
            bb_cols = list(bb.columns)
            # middle is usually index 1, upper index 2
            x["bb_mid"] = bb.iloc[:, 1]
            x["bb_upper"] = bb.iloc[:, 2]
        else:
            x["bb_mid"] = np.nan
            x["bb_upper"] = np.nan

        rsi_len = min(int(getattr(self.cfg, "rsi_len", 14)), max(2, n))
        x["rsi"] = ta.rsi(x["Close"], length=rsi_len)
        macd = ta.macd(
            x["Close"],
            fast=min(int(getattr(self.cfg, "macd_fast", 12)), max(2, n)),
            slow=min(int(getattr(self.cfg, "macd_slow", 26)), max(2, n)),
            signal=min(int(getattr(self.cfg, "macd_signal", 9)), max(2, n)),
        )
        if macd is not None and macd.shape[1] >= 2:
            x["macd"] = macd.iloc[:, 0]
            x["macd_sig"] = macd.iloc[:, 1]
        else:
            x["macd"] = np.nan
            x["macd_sig"] = np.nan

        atr_len = min(int(getattr(self.cfg, "atr_len", 14)), max(2, n))
        x["atr"] = ta.atr(x["High"], x["Low"], x["Close"], length=atr_len)
        x["obv"] = ta.obv(x["Close"], x["Volume"])
        return x.dropna()

    def score(self, candles: pd.DataFrame) -> float:
        x = self._features(candles)
        if x.empty:
            return 0.0
        last = x.iloc[-1]
        eps = 1e-9
        k_norm = getattr(self.cfg, "k_atr_norm", 1.0)
        # Components in [-1,1]
        f_ma = np.tanh((last.ema_fast - last.ema_slow) / (k_norm * last.atr + eps))
        f_bb = np.clip((last.Close - last.bb_mid) / (last.bb_upper - last.bb_mid + eps), -1.0, 1.0)
        f_rsi = np.clip(2.0 * (last.rsi - 50.0) / 50.0, -1.0, 1.0)
        macd_spread = x["macd"] - x["macd_sig"]
        f_macd = np.tanh((last.macd - last.macd_sig) / (macd_spread.std(ddof=0) + eps))
        vol_roll = x["Volume"].rolling(getattr(self.cfg, "vol_len", 20))
        f_vol = np.clip(((x["Volume"] - vol_roll.mean()) / (vol_roll.std(ddof=0) + eps)).iloc[-1], -1.0, 1.0)
        obv_ema = x["obv"].ewm(span=getattr(self.cfg, "obv_span", 20), adjust=False).mean()
        f_obv = np.tanh((last.obv - obv_ema.iloc[-1]) / (np.std(x["obv"] - obv_ema) + eps))

        w = getattr(self.cfg, "weights", None)
        if w is None:
            w = type("W", (), {"ma": 0.3, "bb": 0.15, "rsi": 0.15, "macd": 0.25, "vol": 0.1, "obv": 0.05})()
        s = (
            w.ma * f_ma
            + w.bb * f_bb
            + w.rsi * f_rsi
            + w.macd * f_macd
            + w.vol * f_vol
            + w.obv * f_obv
        )
        max_score = float(getattr(self.cfg, "max_score", 1.0))
        return float(np.clip(s, -max_score, max_score))

    def get_signal(self, market_data: pd.DataFrame, position: Position | None) -> Signal:
        s = self.score(market_data)
        buy_th = float(getattr(self.cfg, "buy_threshold", 0.3))
        sell_th = float(getattr(self.cfg, "sell_threshold", -0.3))
        if s >= buy_th:
            return Signal.BUY
        if s <= sell_th:
            return Signal.SELL
        return Signal.HOLD


