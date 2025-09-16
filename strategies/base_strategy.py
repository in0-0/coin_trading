from abc import ABC, abstractmethod
from typing import Optional
import pandas as pd
from models import Signal, Position

class Strategy(ABC):
    @abstractmethod
    def get_signal(self, market_data: pd.DataFrame, position: Optional[Position]) -> Signal:
        """
        Determine trading signal based on provided market data and current position.
        The strategy should NOT mutate external state; it returns a Signal only.
        """
        pass
