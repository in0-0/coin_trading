from abc import ABC, abstractmethod
from typing import Tuple, Optional
import pandas as pd
from models import Signal, Position

class Strategy(ABC):
    @abstractmethod
    def get_signal(self, market_data: pd.DataFrame, position: Optional[Position]) -> Tuple[Signal, Optional[Position]]:
        pass
