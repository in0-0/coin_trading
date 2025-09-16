# models.py
from datetime import datetime
from enum import Enum

class Signal(Enum):
    HOLD = 0
    BUY = 1
    SELL = 2

class Position:
    """
    거래 포지션의 데이터 모델을 정의합니다.
    """
    def __init__(self, symbol: str, qty: float, entry_price: float, stop_price: float, open_time: datetime = None):
        self.symbol = symbol
        self.qty = qty
        self.entry_price = entry_price
        self.stop_price = stop_price
        self.open_time = open_time or datetime.utcnow()

    def to_dict(self):
        """Position 객체를 JSON 직렬화를 위해 딕셔너리로 변환합니다."""
        return {
            "symbol": self.symbol,
            "qty": self.qty,
            "entry_price": self.entry_price,
            "stop_price": self.stop_price,
            "open_time": self.open_time.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict):
        """딕셔너리에서 Position 객체를 생성합니다."""
        return cls(
            symbol=data["symbol"],
            qty=data["qty"],
            entry_price=data["entry_price"],
            stop_price=data["stop_price"],
            open_time=datetime.fromisoformat(data["open_time"]),
        )

    def __repr__(self):
        return (f"Position(symbol={self.symbol}, qty={self.qty}, "
                f"entry_price={self.entry_price}, stop_price={self.stop_price})")

    # ---- Helper methods ----
    def is_open(self) -> bool:
        return self.qty is not None and self.qty > 0

    def is_long(self) -> bool:
        # We only support long for now; extend later if needed
        return True
