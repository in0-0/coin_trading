from abc import ABC, abstractmethod

import pandas as pd

from models import Position, PositionAction, Signal


class Strategy(ABC):
    @abstractmethod
    def get_signal(self, market_data: pd.DataFrame, position: Position | None) -> Signal:
        """
        Determine trading signal based on provided market data and current position.
        The strategy should NOT mutate external state; it returns a Signal only.
        """
        pass

    def get_position_action(self, market_data: pd.DataFrame, position: Position) -> PositionAction | None:
        """
        Determine position management action (pyramiding, averaging, trailing update, etc.).
        Returns None if no action needed.
        """
        return None
