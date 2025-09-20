"""
Position 관련 비즈니스 로직과 계산을 담당하는 서비스 클래스들

Position 클래스의 과도한 책임을 분리하여 유지보수성과 테스트 용이성을 높입니다.
"""

from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from decimal import Decimal

from .exceptions import ValidationError
from .data_models import PositionData


@dataclass
class PositionLeg:
    """개별 포지션 레그 정보를 담는 데이터 클래스"""
    timestamp: datetime
    side: str  # "BUY" or "SELL"
    quantity: float
    price: float
    order_id: Optional[str] = None
    reason: str = ""  # "entry", "pyramid", "averaging", "partial_exit"


@dataclass
class PositionSummary:
    """포지션 요약 정보"""
    symbol: str
    total_quantity: float
    average_entry_price: float
    total_cost: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    current_price: float
    stop_price: float
    trailing_stop_price: float
    leg_count: int
    partial_exit_count: int


class PositionCalculator:
    """
    포지션 계산 로직을 담당하는 클래스

    평균가 계산, 손익 계산 등의 비즈니스 로직을 분리합니다.
    """

    @staticmethod
    def calculate_average_entry_price(legs: List[PositionLeg]) -> float:
        """
        포지션 레그들로부터 평균 진입가를 계산

        Args:
            legs: 포지션 레그 리스트 (매수 레그만 사용)

        Returns:
            평균 진입가
        """
        if not legs:
            return 0.0

        buy_legs = [leg for leg in legs if leg.side == "BUY"]
        if not buy_legs:
            return 0.0

        total_cost = sum(leg.quantity * leg.price for leg in buy_legs)
        total_quantity = sum(leg.quantity for leg in buy_legs)

        return total_cost / total_quantity if total_quantity > 0 else 0.0

    @staticmethod
    def calculate_total_quantity(legs: List[PositionLeg]) -> float:
        """
        전체 포지션 수량을 계산

        Args:
            legs: 포지션 레그 리스트

        Returns:
            순 수량 (매수 - 매도)
        """
        buy_quantity = sum(leg.quantity for leg in legs if leg.side == "BUY")
        sell_quantity = sum(leg.quantity for leg in legs if leg.side == "SELL")
        return buy_quantity - sell_quantity

    @staticmethod
    def calculate_unrealized_pnl(
        average_entry_price: float,
        current_price: float,
        total_quantity: float
    ) -> tuple[float, float]:
        """
        미실현 손익을 계산

        Args:
            average_entry_price: 평균 진입가
            current_price: 현재가
            total_quantity: 총 수량

        Returns:
            (절대 손익, 손익 비율)
        """
        if average_entry_price <= 0 or total_quantity <= 0:
            return 0.0, 0.0

        pnl_absolute = (current_price - average_entry_price) * total_quantity
        pnl_pct = (current_price - average_entry_price) / average_entry_price

        return pnl_absolute, pnl_pct

    @staticmethod
    def calculate_position_cost(legs: List[PositionLeg]) -> float:
        """
        총 포지션 비용을 계산

        Args:
            legs: 포지션 레그 리스트

        Returns:
            총 비용
        """
        return sum(
            leg.quantity * leg.price
            for leg in legs
            if leg.side == "BUY"
        )

    @staticmethod
    def can_add_position(
        current_legs: List[PositionLeg],
        max_legs: int = 3,
        min_interval_seconds: int = 3600
    ) -> tuple[bool, str]:
        """
        포지션 추가 가능 여부를 확인

        Args:
            current_legs: 현재 포지션 레그들
            max_legs: 최대 레그 수
            min_interval_seconds: 최소 추가 간격 (초)

        Returns:
            (가능여부, 사유)
        """
        if len(current_legs) >= max_legs:
            return False, f"Maximum legs ({max_legs}) reached"

        if not current_legs:
            return True, "First leg allowed"

        last_leg_time = current_legs[-1].timestamp
        time_since_last = (datetime.now(timezone.utc) - last_leg_time).seconds

        if time_since_last < min_interval_seconds:
            return False, f"Minimum interval ({min_interval_seconds}s) not met"

        return True, "Position addition allowed"

    @staticmethod
    def calculate_optimal_trailing_stop(
        current_price: float,
        entry_price: float,
        atr_value: float,
        multiplier: float = 0.5
    ) -> float:
        """
        ATR 기반 최적 트레일링 스탑 가격을 계산

        Args:
            current_price: 현재가
            entry_price: 진입가
            atr_value: ATR 값
            multiplier: ATR 승수

        Returns:
            트레일링 스탑 가격
        """
        # 간단한 ATR 기반 트레일링 스탑 계산
        # 실제로는 더 복잡한 로직이 필요할 수 있음
        stop_distance = atr_value * multiplier
        return current_price - stop_distance


class PositionStateManager:
    """
    포지션 상태 관리 및 검증을 담당하는 클래스
    """

    def __init__(self, symbol: str):
        self.symbol = symbol
        self.legs: List[PositionLeg] = []
        self.partial_exits: List[PositionLeg] = []
        self.status = "ACTIVE"
        self.entry_time = datetime.now(timezone.utc)
        self.trailing_stop_price = 0.0
        self.highest_price = 0.0

    def add_leg(self, leg: PositionLeg) -> None:
        """
        새로운 레그를 추가하고 상태를 업데이트

        Args:
            leg: 추가할 포지션 레그
        """
        self.legs.append(leg)
        self._update_calculated_fields()

    def add_partial_exit(self, exit_leg: PositionLeg) -> None:
        """
        부분 청산 레그를 추가

        Args:
            exit_leg: 청산 레그
        """
        self.partial_exits.append(exit_leg)
        self._update_calculated_fields()

    def update_trailing_stop(self, new_stop_price: float) -> bool:
        """
        트레일링 스탑을 업데이트

        Args:
            new_stop_price: 새로운 스탑 가격

        Returns:
            업데이트 성공 여부
        """
        if new_stop_price > self.trailing_stop_price:
            self.trailing_stop_price = new_stop_price
            return True
        return False

    def _update_calculated_fields(self) -> None:
        """계산된 필드들을 업데이트"""
        self._update_highest_price()
        # 다른 계산 로직들도 여기에 추가 가능

    def _update_highest_price(self) -> None:
        """최고가 업데이트"""
        if self.legs:
            # 현재가는 별도 주입 필요
            # 여기서는 레그들의 최고 매수가로 설정
            self.highest_price = max(
                (leg.price for leg in self.legs if leg.side == "BUY"),
                default=0.0
            )

    def get_summary(self, current_price: float) -> PositionSummary:
        """
        포지션 요약 정보를 생성

        Args:
            current_price: 현재가

        Returns:
            포지션 요약
        """
        total_quantity = PositionCalculator.calculate_total_quantity(self.legs)
        average_entry_price = PositionCalculator.calculate_average_entry_price(self.legs)
        total_cost = PositionCalculator.calculate_position_cost(self.legs)
        pnl_absolute, pnl_pct = PositionCalculator.calculate_unrealized_pnl(
            average_entry_price, current_price, total_quantity
        )

        return PositionSummary(
            symbol=self.symbol,
            total_quantity=total_quantity,
            average_entry_price=average_entry_price,
            total_cost=total_cost,
            unrealized_pnl=pnl_absolute,
            unrealized_pnl_pct=pnl_pct,
            current_price=current_price,
            stop_price=self.trailing_stop_price,  # 기본 스탑 가격
            trailing_stop_price=self.trailing_stop_price,
            leg_count=len(self.legs),
            partial_exit_count=len(self.partial_exits)
        )

    def to_dict(self) -> Dict[str, Any]:
        """직렬화를 위한 딕셔너리 변환"""
        return {
            "symbol": self.symbol,
            "legs": [
                {
                    "timestamp": leg.timestamp.isoformat(),
                    "side": leg.side,
                    "quantity": leg.quantity,
                    "price": leg.price,
                    "order_id": leg.order_id,
                    "reason": leg.reason
                }
                for leg in self.legs
            ],
            "partial_exits": [
                {
                    "timestamp": leg.timestamp.isoformat(),
                    "side": leg.side,
                    "quantity": leg.quantity,
                    "price": leg.price,
                    "order_id": leg.order_id,
                    "reason": leg.reason
                }
                for leg in self.partial_exits
            ],
            "status": self.status,
            "entry_time": self.entry_time.isoformat(),
            "trailing_stop_price": self.trailing_stop_price,
            "highest_price": self.highest_price
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], symbol: str) -> 'PositionStateManager':
        """
        딕셔너리로부터 PositionStateManager 생성

        Args:
            data: 직렬화된 데이터
            symbol: 심볼

        Returns:
            PositionStateManager 인스턴스
        """
        manager = cls(symbol)

        # 레그 데이터 로드
        for leg_data in data.get("legs", []):
            leg = PositionLeg(
                timestamp=datetime.fromisoformat(leg_data["timestamp"]),
                side=leg_data["side"],
                quantity=leg_data["quantity"],
                price=leg_data["price"],
                order_id=leg_data.get("order_id"),
                reason=leg_data.get("reason", "entry")
            )
            manager.legs.append(leg)

        # 부분 청산 데이터 로드
        for exit_data in data.get("partial_exits", []):
            exit_leg = PositionLeg(
                timestamp=datetime.fromisoformat(exit_data["timestamp"]),
                side=exit_data["side"],
                quantity=exit_data["quantity"],
                price=exit_data["price"],
                order_id=exit_data.get("order_id"),
                reason=exit_data.get("reason", "partial_exit")
            )
            manager.partial_exits.append(exit_leg)

        # 기타 상태 로드
        manager.status = data.get("status", "ACTIVE")
        manager.entry_time = datetime.fromisoformat(data.get("entry_time", datetime.now(timezone.utc).isoformat()))
        manager.trailing_stop_price = data.get("trailing_stop_price", 0.0)
        manager.highest_price = data.get("highest_price", 0.0)

        return manager

    def validate(self) -> List[str]:
        """
        포지션 상태의 유효성을 검증

        Returns:
            검증 오류 메시지 리스트 (비어있으면 유효함)
        """
        errors = []

        # 기본 수량 검증
        total_quantity = PositionCalculator.calculate_total_quantity(self.legs)
        if total_quantity <= 0 and self.status == "ACTIVE":
            errors.append("Active position must have positive quantity")

        # 레그 일관성 검증
        if len(self.legs) > 0:
            # 첫 번째 레그는 반드시 매수여야 함
            if self.legs[0].side != "BUY":
                errors.append("First leg must be a buy")

        # 스탑 가격 검증
        if self.trailing_stop_price <= 0 and self.status == "ACTIVE":
            errors.append("Active position must have valid stop price")

        return errors


class PositionService:
    """
    포지션 관련 고수준 비즈니스 로직을 담당하는 서비스 클래스
    """

    def __init__(self):
        self.calculator = PositionCalculator()

    def create_position(
        self,
        symbol: str,
        quantity: float,
        entry_price: float,
        stop_price: float,
        timestamp: Optional[datetime] = None
    ) -> PositionStateManager:
        """
        새로운 포지션을 생성

        Args:
            symbol: 심볼
            quantity: 수량
            entry_price: 진입가
            stop_price: 스탑 가격
            timestamp: 진입 시간

        Returns:
            생성된 포지션 매니저
        """
        manager = PositionStateManager(symbol)
        manager.entry_time = timestamp or datetime.now(timezone.utc)

        # 초기 레그 생성
        initial_leg = PositionLeg(
            timestamp=manager.entry_time,
            side="BUY",
            quantity=quantity,
            price=entry_price,
            reason="entry"
        )

        manager.add_leg(initial_leg)
        manager.trailing_stop_price = stop_price
        manager.highest_price = entry_price

        return manager

    def can_add_to_position(
        self,
        position: PositionStateManager,
        current_time: Optional[datetime] = None
    ) -> tuple[bool, str]:
        """
        포지션에 추가할 수 있는지 확인

        Args:
            position: 대상 포지션
            current_time: 현재 시간 (None이면 현재 시간 사용)

        Returns:
            (가능여부, 사유)
        """
        return PositionCalculator.can_add_position(
            position.legs,
            max_legs=position.max_pyramid_legs if hasattr(position, 'max_pyramid_legs') else 3,
            min_interval_seconds=position.min_add_interval if hasattr(position, 'min_add_interval') else 3600
        )

    def calculate_position_value(
        self,
        position: PositionStateManager,
        current_price: float
    ) -> Dict[str, float]:
        """
        포지션의 현재 가치를 계산

        Args:
            position: 대상 포지션
            current_price: 현재가

        Returns:
            가치 정보 딕셔너리
        """
        summary = position.get_summary(current_price)

        return {
            "total_value": summary.total_quantity * current_price,
            "total_cost": summary.total_cost,
            "unrealized_pnl": summary.unrealized_pnl,
            "unrealized_pnl_pct": summary.unrealized_pnl_pct,
            "average_entry": summary.average_entry_price
        }
