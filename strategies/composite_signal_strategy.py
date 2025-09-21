
import numpy as np
import pandas as pd
import pandas_ta as ta

from models import Position, Signal, PositionAction
from strategies.base_strategy import Strategy


class CompositeSignalStrategy(Strategy):
    def __init__(self, config=None, **kwargs):
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

        # weights가 딕셔너리인지 객체인지 확인
        if isinstance(w, dict):
            # 딕셔너리인 경우
            w_ma = w.get("ma", 0.3)
            w_bb = w.get("bb", 0.15)
            w_rsi = w.get("rsi", 0.15)
            w_macd = w.get("macd", 0.25)
            w_vol = w.get("vol", 0.1)
            w_obv = w.get("obv", 0.05)
        else:
            # 객체인 경우
            w_ma = getattr(w, "ma", 0.3)
            w_bb = getattr(w, "bb", 0.15)
            w_rsi = getattr(w, "rsi", 0.15)
            w_macd = getattr(w, "macd", 0.25)
            w_vol = getattr(w, "vol", 0.1)
            w_obv = getattr(w, "obv", 0.05)

        s = (
            w_ma * f_ma
            + w_bb * f_bb
            + w_rsi * f_rsi
            + w_macd * f_macd
            + w_vol * f_vol
            + w_obv * f_obv
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

    def get_position_action(self, market_data: pd.DataFrame, position: Position) -> PositionAction | None:
        """
        Phase 2, 3 & 4: Composite 전략의 포지션 액션 처리
        Composite 스코어 기반으로 불타기, 트레일링 스탑, 부분 청산 결정
        """
        if position is None or not position.legs:
            return None

        # 현재가 추출
        if market_data is None or market_data.empty:
            return None

        current_price = float(market_data["Close"].iloc[-1])

        # ATR 추출 (트레일링 스탑 계산용)
        if "atr" not in market_data.columns:
            # ATR 계산
            market_data = market_data.copy()
            atr_len = min(int(getattr(self.cfg, "atr_len", 14)), max(2, len(market_data)))
            market_data['atr'] = ta.atr(market_data['High'], market_data['Low'], market_data['Close'], length=atr_len)
            # ATR 계산 후 NaN 제거
            market_data = market_data.dropna()

        if market_data.empty or "atr" not in market_data.columns:
            return None

        atr = float(market_data["atr"].iloc[-1])
        if atr <= 0 or pd.isna(atr):
            return None

        # Composite 스코어 계산
        score = self.score(market_data)

        # 기본 지출액 계산
        base_spend = position.qty * position.entry_price * 0.5

        # Phase 2: 불타기 (스코어가 매우 높을 때)
        if score > 0.7:  # 강한 상승 신호
            return PositionAction(
                action_type="BUY_ADD",
                price=None,
                metadata={
                    "pyramid_size": base_spend,
                    "reason": "composite_pyramid",
                    "score": score
                }
            )

        # Phase 2: 물타기 (스코어가 매우 낮지만 하락폭이 제한적일 때)
        if score < -0.5 and (position.entry_price - current_price) / position.entry_price < 0.1:
            return PositionAction(
                action_type="BUY_ADD",
                price=None,
                metadata={
                    "averaging_size": base_spend,
                    "reason": "composite_averaging",
                    "score": score
                }
            )

        # Phase 3: 트레일링 스탑 업데이트
        # 현재 최고가 대비 ATR 기반 트레일링 스탑
        highest_price = max(leg.price for leg in position.legs)
        trailing_distance = atr * 1.5  # ATR의 1.5배
        new_trail_price = highest_price - trailing_distance

        # 현재 트레일링 스탑보다 높으면 업데이트
        if new_trail_price > position.trailing_stop_price:
            return PositionAction(
                action_type="UPDATE_TRAIL",
                price=new_trail_price,
                metadata={
                    "highest_price": highest_price,
                    "trailing_distance": trailing_distance,
                    "reason": "composite_trailing_update"
                }
            )

        # Phase 4: 부분 청산 (스코어가 약해질 때)
        if score < 0.2 and score > -0.2:  # 중립 영역
            profit_pct = (current_price - position.entry_price) / position.entry_price
            if profit_pct > 0.05:  # 5% 이상 수익 시
                return PositionAction(
                    action_type="SELL_PARTIAL",
                    price=None,
                    metadata={
                        "exit_qty": position.qty * 0.3,  # 30% 청산
                        "qty_ratio": 0.3,
                        "reason": "composite_partial_exit",
                        "profit_pct": profit_pct,
                        "score": score
                    }
                )

        return None


