"""
PositionManager: 불타기(Pyramiding)와 물타기(Averaging Down) 로직 관리
"""

from datetime import UTC, datetime

from models import Position, PositionAction


class PositionManager:
    """불타기와 물타기 전략을 관리하는 클래스"""

    def __init__(self):
        # 불타기 설정 (승자 편승 추가 매수)
        self.pyramid_config = {
            "min_profit_pct": 0.03,    # 3% 수익 시 불타기 가능
            "max_legs": 3,             # 최대 불타기 횟수
            "size_progression": [1.0, 0.7, 0.5]  # 각 레그별 사이즈 비율
        }

        # 물타기 설정 (손실 완화 추가 매수)
        self.averaging_config = {
            "max_loss_pct": -0.05,     # -5% 손실 시 물타기 가능
            "max_legs": 2,             # 최대 물타기 횟수
            "recovery_target": 0.0     # 평단 회복 목표
        }

    def should_pyramid(self, position: Position, current_price: float) -> bool:
        """
        불타기 조건 확인
        - 포지션 추가 가능 여부
        - 최소 수익률 도달
        """
        if not position.can_add_position(datetime.now(UTC)):
            return False

        unrealized_pct = (current_price - position.entry_price) / position.entry_price
        return unrealized_pct >= self.pyramid_config["min_profit_pct"]

    def should_average_down(self, position: Position, current_price: float) -> bool:
        """
        물타기 조건 확인
        - 포지션 추가 가능 여부
        - 최대 손실률 도달
        """
        if not position.can_add_position(datetime.now(UTC)):
            return False

        unrealized_pct = (current_price - position.entry_price) / position.entry_price
        return unrealized_pct <= self.averaging_config["max_loss_pct"]

    def calculate_pyramid_size(self, position: Position, base_spend: float) -> float:
        """
        불타기 사이즈 계산
        - 현재 레그 수에 따른 사이즈 조정
        """
        leg_count = len(position.legs)
        if leg_count >= len(self.pyramid_config["size_progression"]):
            return 0.0

        size_ratio = self.pyramid_config["size_progression"][leg_count]
        return base_spend * size_ratio

    def calculate_averaging_size(self, position: Position, base_spend: float) -> float:
        """
        물타기 사이즈 계산
        - 손실 정도에 따른 사이즈 조정 (더 큰 손실 = 더 큰 사이즈)
        """
        # 현재 구현은 간단한 버전 (향후 고도화 가능)
        return base_spend * 0.5

    def get_pyramid_action(self, position: Position, current_price: float, base_spend: float) -> PositionAction | None:
        """불타기 액션 생성"""
        if not self.should_pyramid(position, current_price):
            return None

        pyramid_size = self.calculate_pyramid_size(position, base_spend)
        if pyramid_size <= 0:
            return None

        return PositionAction(
            action_type="BUY_ADD",
            qty_ratio=0.5,  # 현재는 고정 (향후 동적 계산)
            reason="pyramiding",
            metadata={"base_spend": base_spend, "pyramid_size": pyramid_size}
        )

    def get_averaging_action(self, position: Position, current_price: float, base_spend: float) -> PositionAction | None:
        """물타기 액션 생성"""
        if not self.should_average_down(position, current_price):
            return None

        averaging_size = self.calculate_averaging_size(position, base_spend)
        if averaging_size <= 0:
            return None

        return PositionAction(
            action_type="BUY_ADD",
            qty_ratio=0.3,  # 현재는 고정 (향후 동적 계산)
            reason="averaging_down",
            metadata={"base_spend": base_spend, "averaging_size": averaging_size}
        )
