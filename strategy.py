from abc import ABC, abstractmethod
import pandas as pd

def calculate_rsi(df: pd.DataFrame, period=14) -> pd.Series:
    """RSI(상대강도지수)를 계산합니다."""
    delta = df['Close'].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(window=period, min_periods=1).mean()
    avg_loss = loss.rolling(window=period, min_periods=1).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

class Strategy(ABC):
    @abstractmethod
    def apply_strategy(self, df: pd.DataFrame) -> pd.DataFrame:
        pass

class MovingAverageCrossStrategy(Strategy):
    """단순 이동평균 교차 전략

    이 전략은 자체적으로 매수(1)와 매도(-1) 신호를 모두 생성하여 완결된 형태입니다.
    """
    def __init__(self, short_window=20, long_window=50):
        self.short_window = short_window
        self.long_window = long_window

    def apply_strategy(self, df: pd.DataFrame) -> pd.DataFrame:
        df[f'MA_{self.short_window}'] = df['Close'].rolling(window=self.short_window).mean()
        df[f'MA_{self.long_window}'] = df['Close'].rolling(window=self.long_window).mean()
        df['Signal'] = 0
        df.loc[df[f'MA_{self.short_window}'] > df[f'MA_{self.long_window}'], 'Signal'] = 1
        df.loc[df[f'MA_{self.short_window}'] < df[f'MA_{self.long_window}'], 'Signal'] = -1
        return df

class BuyAndHoldStrategy(Strategy):
    """단순 매수 후 보유 전략

    매수 신호(1)만 생성하며, 별도의 매도 로직 없이 데이터 끝까지 보유합니다.
    """
    def apply_strategy(self, df: pd.DataFrame) -> pd.DataFrame:
        df['Signal'] = 1
        return df

class VolatilityMomentumStrategy(Strategy):
    """변동성 돌파 + 모멘텀 복합 전략

    매수 신호(1)만 생성합니다.
    **매도(청산) 로직은 Backtester가 config.py의 exit_params에 따라 처리합니다.**
    (예: 손절, 타임컷 등)
    """
    def __init__(self, k=0.5, rsi_period=14, rsi_threshold=50):
        self.k = k
        self.rsi_period = rsi_period
        self.rsi_threshold = rsi_threshold

    def apply_strategy(self, df: pd.DataFrame) -> pd.DataFrame:
        df['Range'] = (df['High'].shift(1) - df['Low'].shift(1))
        df['Breakout_Target'] = df['Open'] + df['Range'] * self.k
        df[f'RSI_{self.rsi_period}'] = calculate_rsi(df, self.rsi_period)
        df['Signal'] = 0
        df.loc[(df['High'] > df['Breakout_Target']) & (df[f'RSI_{self.rsi_period}'] > self.rsi_threshold), 'Signal'] = 1
        return df

class MAReversionStrategy(Strategy):
    """이동평균 리버전 전략

    매수 신호(1)만 생성합니다.
    **매도(청산) 로직은 Backtester가 config.py의 exit_params에 따라 처리합니다.**
    (예: 익절, 손절, 이평선 도달 등)
    """
    def __init__(self, ma_period=20, reversion_pct=0.05):
        self.ma_period = ma_period
        self.reversion_pct = reversion_pct

    def apply_strategy(self, df: pd.DataFrame) -> pd.DataFrame:
        df[f'MA_{self.ma_period}'] = df['Close'].rolling(window=self.ma_period).mean()
        df['Reversion_Target'] = df[f'MA_{self.ma_period}'] * (1 - self.reversion_pct)
        df['Signal'] = 0
        df.loc[df['Close'] < df['Reversion_Target'], 'Signal'] = 1
        return df

class StrategyFactory:
    def __init__(self):
        self._strategies = {
            "ma_cross": MovingAverageCrossStrategy,
            "buy_hold": BuyAndHoldStrategy,
            "vol_momentum": VolatilityMomentumStrategy,
            "ma_reversion": MAReversionStrategy
        }

    def get_strategy(self, name: str, **kwargs) -> Strategy:
        strategy_class = self._strategies.get(name)
        if not strategy_class:
            raise ValueError(f"Strategy '{name}' not found.")
        return strategy_class(**kwargs)