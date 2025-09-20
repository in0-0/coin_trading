# models.py
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum


class Signal(Enum):
    HOLD = 0
    BUY = 1
    SELL = 2
    # 새로운 신호들 (Phase 1)
    BUY_NEW = 3      # 신규 진입
    BUY_ADD = 4      # 불타기/물타기
    SELL_PARTIAL = 5 # 부분 청산
    SELL_ALL = 6     # 전량 청산
    UPDATE_TRAIL = 7 # 트레일링 업데이트

@dataclass
class PositionAction:
    """포지션 관리 액션"""
    action_type: str  # "BUY_ADD", "SELL_PARTIAL", "UPDATE_TRAIL"
    qty_ratio: float = 1.0  # 0.0 ~ 1.0
    price: float | None = None
    reason: str = ""
    metadata: dict = field(default_factory=dict)

@dataclass
class PositionLeg:
    """각 매수/매도 레그 추적"""
    timestamp: datetime
    side: str  # "BUY" or "SELL"
    qty: float
    price: float
    order_id: str | None = None
    reason: str = ""  # "entry", "pyramid", "averaging", "partial_exit"

class Position:
    """
    거래 포지션의 데이터 모델을 정의합니다.
    향상된 버전: 여러 레그 관리, 트레일링 스탑, 부분 청산 지원
    """
    def __init__(self, symbol: str, qty: float = 0.0, entry_price: float = 0.0, stop_price: float = 0.0, open_time: datetime = None):
        self.symbol = symbol
        self.legs: list[PositionLeg] = []
        self.partial_exits: list[PositionLeg] = []
        self.status = "ACTIVE"
        self.entry_time = open_time or datetime.now(UTC)

        # 누적 계산 속성 (호환성 유지)
        self.qty = qty
        self.entry_price = entry_price
        self.stop_price = stop_price

        # 트레일링 스탑 관리
        self.trailing_stop_price = stop_price
        self.highest_price = entry_price if entry_price > 0 else 0.0

        # 포지션 한도 설정
        self.max_pyramid_legs = 3  # 최대 불타기 횟수
        self.min_add_interval = 3600  # 추가 매수 최소 간격 (초)

        # 초기 레그 추가 (기존 호환성 위해)
        if qty > 0 and entry_price > 0:
            initial_leg = PositionLeg(
                timestamp=self.entry_time,
                side="BUY",
                qty=qty,
                price=entry_price,
                reason="entry"
            )
            self.legs.append(initial_leg)
            self._recalculate_totals()

    def _recalculate_totals(self):
        """레그들로부터 누적 수량과 평단가 재계산"""
        if not self.legs:
            self.qty = 0.0
            self.entry_price = 0.0
            return

        total_cost = 0.0
        total_qty = 0.0

        for leg in self.legs:
            if leg.side == "BUY":
                total_cost += leg.qty * leg.price
                total_qty += leg.qty

        if total_qty > 0:
            self.qty = total_qty
            self.entry_price = total_cost / total_qty
        else:
            self.qty = 0.0
            self.entry_price = 0.0

    @property
    def unrealized_pnl_pct(self) -> float:
        """현재 미실현 손익 비율 (현재가는 별도 제공 필요)"""
        if self.entry_price <= 0:
            return 0.0
        # 실제 계산은 현재가를 받아서 해야 함
        return 0.0  # 현재가는 외부에서 주입

    def can_add_position(self, current_time: datetime) -> bool:
        """추가 포지션 가능 여부 확인"""
        if len(self.legs) >= self.max_pyramid_legs:
            return False
        if not self.legs:
            return True
        last_leg_time = self.legs[-1].timestamp
        if (current_time - last_leg_time).seconds < self.min_add_interval:
            return False
        return True

    def add_leg(self, leg: PositionLeg):
        """새 레그 추가"""
        self.legs.append(leg)
        self._recalculate_totals()

    def update_trailing_stop(self, new_price: float):
        """트레일링 스탑 업데이트"""
        if new_price > self.trailing_stop_price:
            self.trailing_stop_price = new_price

    def get_remaining_qty(self) -> float:
        """부분 청산 후 남은 수량"""
        return self.qty

    def to_dict(self):
        """Position 객체를 JSON 직렬화를 위해 딕셔너리로 변환합니다."""
        # 기존 호환성을 위해 간단한 형태 유지
        return {
            "symbol": self.symbol,
            "qty": self.qty,
            "entry_price": self.entry_price,
            "stop_price": self.trailing_stop_price,  # 트레일링 스탑 사용
            "open_time": self.entry_time.isoformat(),
            # 향상된 정보는 별도 저장 (향후 확장 가능)
            "legs": [{"timestamp": leg.timestamp.isoformat(),
                      "side": leg.side,
                      "qty": leg.qty,
                      "price": leg.price,
                      "reason": leg.reason} for leg in self.legs],
            "trailing_stop_price": self.trailing_stop_price,
            "highest_price": self.highest_price,
        }

    @classmethod
    def from_dict(cls, data: dict):
        """딕셔너리에서 Position 객체를 생성합니다."""
        # 향상된 정보가 있는 경우
        legs_data = data.get("legs", [])
        legs = []
        for leg_data in legs_data:
            legs.append(PositionLeg(
                timestamp=datetime.fromisoformat(leg_data["timestamp"]),
                side=leg_data["side"],
                qty=leg_data["qty"],
                price=leg_data["price"],
                reason=leg_data.get("reason", "entry")
            ))

        position = cls(
            symbol=data["symbol"],
            qty=data.get("qty", 0.0),
            entry_price=data.get("entry_price", 0.0),
            stop_price=data.get("trailing_stop_price", data.get("stop_price", 0.0)),
            open_time=datetime.fromisoformat(data["open_time"]),
        )

        # 향상된 정보 로드
        if legs:
            position.legs = legs
            position._recalculate_totals()

        position.trailing_stop_price = data.get("trailing_stop_price", position.trailing_stop_price)
        position.highest_price = data.get("highest_price", position.highest_price)

        return position

    def __repr__(self):
        return (f"Position(symbol={self.symbol}, qty={self.qty}, "
                f"entry_price={self.entry_price}, stop_price={self.stop_price})")

    # ---- Helper methods ----
    def is_open(self) -> bool:
        return self.qty is not None and self.qty > 0

    def is_long(self) -> bool:
        # We only support long for now; extend later if needed
        return True
