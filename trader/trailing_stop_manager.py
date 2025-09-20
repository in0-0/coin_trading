"""
TrailingStopManager: 트레일링 스탑 상향 갱신 로직 관리
"""

from models import Position, PositionAction


class TrailingStopManager:
    """트레일링 스탑 전략을 관리하는 클래스"""

    def __init__(self):
        # 트레일링 스탑 설정
        self.config = {
            "activation_profit": 0.02,  # 2% 수익 시 활성화
            "atr_multiplier": 1.0,      # ATR 배수
            "step_up_pct": 0.01         # 단계적 상향 비율 (1%)
        }

    def should_activate_trailing(self, position: Position, current_price: float) -> bool:
        """
        트레일링 스탑 활성화 조건 확인
        - 최소 수익률 도달
        - 현재가가 최고가보다 높은지 확인
        """
        unrealized_pct = (current_price - position.entry_price) / position.entry_price
        return unrealized_pct >= self.config["activation_profit"]

    def update_trailing_stop(self, position: Position, current_price: float, atr: float) -> float:
        """
        새로운 트레일링 스탑 가격 계산
        - ATR 기반 동적 트레일링
        - 최고가 업데이트 시 스탑 상향
        """
        if not self.should_activate_trailing(position, current_price):
            return position.trailing_stop_price

        # 최고가 업데이트
        if current_price > position.highest_price:
            position.highest_price = current_price

        # ATR 기반 트레일링 스탑 계산
        new_trail = position.highest_price * (1 - self.config["atr_multiplier"] * atr / current_price)

        # 기존 스탑보다 높으면 상향
        if new_trail > position.trailing_stop_price:
            return new_trail

        return position.trailing_stop_price

    def should_update_trailing(self, position: Position, current_price: float, atr: float) -> bool:
        """
        트레일링 스탑 업데이트 필요 여부 확인
        """
        if not self.should_activate_trailing(position, current_price):
            return False

        new_trail = self.update_trailing_stop(position, current_price, atr)
        return new_trail > position.trailing_stop_price

    def get_trailing_update_action(self, position: Position, current_price: float, atr: float) -> PositionAction | None:
        """트레일링 스탑 업데이트 액션 생성"""
        if not self.should_update_trailing(position, current_price, atr):
            return None

        new_trail = self.update_trailing_stop(position, current_price, atr)
        return PositionAction(
            action_type="UPDATE_TRAIL",
            price=new_trail,
            reason="trailing_stop_update",
            metadata={
                "old_trail": position.trailing_stop_price,
                "new_trail": new_trail,
                "highest_price": position.highest_price,
                "current_price": current_price,
                "atr": atr
            }
        )
