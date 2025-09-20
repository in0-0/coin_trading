"""
PartialExitManager: 부분 청산 로직 관리
"""

from typing import Any

from models import Position, PositionAction


class PartialExitManager:
    """부분 청산 전략을 관리하는 클래스"""

    def __init__(self):
        # 부분 청산 레벨 설정
        self.exit_levels = [
            {"profit_pct": 0.05, "exit_ratio": 0.3, "level": 1},  # 5% 수익 시 30% 청산
            {"profit_pct": 0.10, "exit_ratio": 0.3, "level": 2},  # 10% 수익 시 30% 청산
            {"profit_pct": 0.15, "exit_ratio": 0.4, "level": 3},  # 15% 수익 시 40% 청산
            {"profit_pct": 0.20, "exit_ratio": 0.3, "level": 4},  # 20% 수익 시 30% 청산
        ]

    def should_partial_exit(self, position: Position, current_price: float) -> dict[str, Any] | None:
        """
        부분 청산 조건 확인
        - 미실현 수익률 계산
        - 해당 레벨에서 이미 청산했는지 확인
        """
        unrealized_pct = (current_price - position.entry_price) / position.entry_price

        for level in self.exit_levels:
            if unrealized_pct >= level["profit_pct"]:
                # 이미 해당 레벨에서 청산했는지 확인
                if not self._already_exited_at_level(position, level["level"]):
                    return level

        return None

    def _already_exited_at_level(self, position: Position, level: int) -> bool:
        """
        해당 레벨에서 이미 부분 청산했는지 확인
        """
        for leg in position.partial_exits:
            if leg.reason.startswith(f"partial_exit_level_{level}"):
                return True
        return False

    def calculate_exit_qty(self, position: Position, exit_ratio: float) -> float:
        """
        부분 청산 수량 계산
        - 현재 남은 수량의 비율로 계산
        """
        return position.get_remaining_qty() * exit_ratio

    def get_partial_exit_action(self, position: Position, current_price: float) -> PositionAction | None:
        """부분 청산 액션 생성"""
        exit_level = self.should_partial_exit(position, current_price)
        if not exit_level:
            return None

        exit_qty = self.calculate_exit_qty(position, exit_level["exit_ratio"])
        if exit_qty <= 0:
            return None

        return PositionAction(
            action_type="SELL_PARTIAL",
            qty_ratio=exit_level["exit_ratio"],
            reason=f"partial_exit_level_{exit_level['level']}",
            metadata={
                "exit_level": exit_level["level"],
                "profit_pct": exit_level["profit_pct"],
                "exit_ratio": exit_level["exit_ratio"],
                "exit_qty": exit_qty,
                "current_price": current_price,
                "unrealized_pct": (current_price - position.entry_price) / position.entry_price
            }
        )
