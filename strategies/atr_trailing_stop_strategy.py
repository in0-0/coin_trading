from strategies.base_strategy import Strategy
from models import Signal, Position
from typing import Optional
import pandas as pd
import pandas_ta as ta

TITLE_COLUMNS = {"Open": "Open", "High": "High", "Low": "Low", "Close": "Close"}

class ATRTrailingStopStrategy(Strategy):
    def __init__(self, symbol: str, atr_multiplier: float, risk_per_trade: float):
        self.symbol = symbol
        self.atr_multiplier = atr_multiplier
        self.risk_per_trade = risk_per_trade

    def get_signal(self, market_data: pd.DataFrame, position: Optional[Position]) -> Signal:
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
