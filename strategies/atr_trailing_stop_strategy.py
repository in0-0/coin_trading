from strategies.base_strategy import Strategy
from models import Signal, Position
from state_manager import StateManager
import pandas as pd
import pandas_ta as ta

class ATRTrailingStopStrategy(Strategy):
    def __init__(self, symbol: str, atr_multiplier: float, risk_per_trade: float, state_manager: StateManager):
        self.symbol = symbol
        self.atr_multiplier = atr_multiplier
        self.risk_per_trade = risk_per_trade
        self.state_manager = state_manager

    def get_signal(self, market_data: pd.DataFrame) -> Signal:
        if market_data.empty:
            return Signal.HOLD

        self._calculate_indicators(market_data)
        position = self.state_manager.get_position()
        return self._determine_signal(market_data, position)

    def _calculate_indicators(self, market_data: pd.DataFrame):
        market_data['atr'] = ta.atr(market_data['high'], market_data['low'], market_data['close'])
        market_data['rsi'] = ta.rsi(market_data['close'])
        market_data.dropna(inplace=True)

    def _determine_signal(self, market_data: pd.DataFrame, position: Position) -> Signal:
        latest_data = market_data.iloc[-1]
        
        if position.is_open():
            return self._handle_open_position(latest_data, position)
        else:
            return self._handle_no_position(latest_data)

    def _handle_open_position(self, latest_data, position: Position) -> Signal:
        if position.is_long():
            stop_loss = latest_data['close'] - latest_data['atr'] * self.atr_multiplier
            if latest_data['close'] < position.stop_loss:
                self.state_manager.update_position(Position(symbol=self.symbol))
                return Signal.SELL
            else:
                new_stop_loss = max(position.stop_loss, stop_loss)
                self.state_manager.update_position(Position(
                    symbol=self.symbol, 
                    is_long=True, 
                    entry_price=position.entry_price, 
                    stop_loss=new_stop_loss
                ))
        else: # Short position
            stop_loss = latest_data['close'] + latest_data['atr'] * self.atr_multiplier
            if latest_data['close'] > position.stop_loss:
                self.state_manager.update_position(Position(symbol=self.symbol))
                return Signal.BUY
            else:
                new_stop_loss = min(position.stop_loss, stop_loss)
                self.state_manager.update_position(Position(
                    symbol=self.symbol, 
                    is_long=False, 
                    entry_price=position.entry_price, 
                    stop_loss=new_stop_loss
                ))
        return Signal.HOLD

    def _handle_no_position(self, latest_data) -> Signal:
        if latest_data['rsi'] > 70:
            stop_loss = latest_data['close'] - latest_data['atr'] * self.atr_multiplier
            self.state_manager.update_position(Position(
                symbol=self.symbol, 
                is_long=True, 
                entry_price=latest_data['close'], 
                stop_loss=stop_loss
            ))
            return Signal.BUY
        elif latest_data['rsi'] < 30:
            stop_loss = latest_data['close'] + latest_data['atr'] * self.atr_multiplier
            self.state_manager.update_position(Position(
                symbol=self.symbol, 
                is_long=False, 
                entry_price=latest_data['close'], 
                stop_loss=stop_loss
            ))
            return Signal.SELL
        return Signal.HOLD
