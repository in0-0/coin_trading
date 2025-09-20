
import pandas as pd
import pandas_ta as ta

from models import Position, PositionAction, Signal
from strategies.base_strategy import Strategy
from trader.partial_exit_manager import PartialExitManager
from trader.position_manager import PositionManager
from trader.trailing_stop_manager import TrailingStopManager

TITLE_COLUMNS = {"Open": "Open", "High": "High", "Low": "Low", "Close": "Close"}

class ATRTrailingStopStrategy(Strategy):
    def __init__(self, symbol: str, atr_multiplier: float, risk_per_trade: float):
        self.symbol = symbol
        self.atr_multiplier = atr_multiplier
        self.risk_per_trade = risk_per_trade
        # Phase 2: PositionManager 주입
        self.position_manager = PositionManager()
        # Phase 3: TrailingStopManager 주입
        self.trailing_manager = TrailingStopManager()
        # Phase 4: PartialExitManager 주입
        self.partial_exit_manager = PartialExitManager()

    def get_position_action(self, market_data: pd.DataFrame, position: Position) -> PositionAction | None:
        """
        Phase 2, 3 & 4: 불타기/물타기 + 트레일링 스탑 + 부분 청산 로직 구현
        """
        if position is None or not position.legs:
            return None

        # 현재가 추출
        if market_data is None or market_data.empty:
            return None

        current_price = float(market_data["Close"].iloc[-1])

        # ATR 추출 (트레일링 스탑 계산용)
        if "atr" not in market_data.columns:
            return None

        atr = float(market_data["atr"].iloc[-1])
        if atr <= 0:
            return None

        # 기본 지출액 계산 (단순 버전)
        base_spend = position.qty * position.entry_price * 0.5  # 현재 포지션의 50%

        # Phase 2: 불타기 우선 체크
        pyramid_action = self.position_manager.get_pyramid_action(position, current_price, base_spend)
        if pyramid_action:
            return pyramid_action

        # Phase 2: 물타기 체크
        averaging_action = self.position_manager.get_averaging_action(position, current_price, base_spend)
        if averaging_action:
            return averaging_action

        # Phase 3: 트레일링 스탑 업데이트 체크
        trailing_action = self.trailing_manager.get_trailing_update_action(position, current_price, atr)
        if trailing_action:
            return trailing_action

        # Phase 4: 부분 청산 체크
        partial_exit_action = self.partial_exit_manager.get_partial_exit_action(position, current_price)
        if partial_exit_action:
            return partial_exit_action

        return None

    def get_signal(self, market_data: pd.DataFrame, position: Position | None) -> Signal:
        if market_data is None or market_data.empty:
            return Signal.HOLD

        self._calculate_indicators(market_data)
        latest = market_data.iloc[-1]

        # If no position, entry rules using Title case columns
        if position is None or not position.is_open():
            # Example entry: RSI oversold/overbought with ATR-based stop
            if latest['rsi'] > 70:
                return Signal.SELL  # Overbought -> sell signal if we supported shorts; for long-only, HOLD
            if latest['rsi'] < 30:
                return Signal.BUY
            return Signal.HOLD

        # Manage existing long position with trailing stop
        if position.is_long():
            trailing_stop = float(latest['Close'] - latest['atr'] * self.atr_multiplier)
            if latest['Close'] <= position.stop_price:
                return Signal.SELL
            # Stop update is handled by trader using returned market data/logic; strategy only signals
            return Signal.HOLD

        return Signal.HOLD

    def _calculate_indicators(self, market_data: pd.DataFrame) -> None:
        # Ensure Title case columns
        for col in ["High", "Low", "Close"]:
            if col not in market_data.columns and col.lower() in market_data.columns:
                market_data[col] = market_data[col.lower()]
        market_data['atr'] = ta.atr(market_data['High'], market_data['Low'], market_data['Close'])
        market_data['rsi'] = ta.rsi(market_data['Close'])
        market_data.dropna(inplace=True)
