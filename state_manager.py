import json
import os
import logging
from typing import Dict
from models import Position  # Position 클래스를 models.py에서 임포트

class StateManager:
    """
    거래 상태(포지션)를 안전하게 파일에 저장하고 불러오는 역할을 합니다.
    """
    def __init__(self, state_file="live_positions.json"):
        self.state_file = state_file

    def save_positions(self, positions: Dict[str, Position]):
        """
        현재 포지션 딕셔너리를 JSON 파일에 저장합니다.
        """
        try:
            state_data = {symbol: pos.to_dict() for symbol, pos in positions.items()}
            with open(self.state_file, "w") as f:
                json.dump(state_data, f, indent=4)
        except IOError as e:
            logging.error(f"Error saving state to {self.state_file}: {e}")

    def load_positions(self) -> Dict[str, Position]:
        """
        파일에서 포지션 정보를 불러와 Position 객체 딕셔너리로 복원합니다.
        """
        if not os.path.exists(self.state_file):
            return {}
        try:
            with open(self.state_file, "r") as f:
                state_data = json.load(f)
                return {
                    symbol: Position.from_dict(pos_data)
                    for symbol, pos_data in state_data.items()
                }
        except (IOError, json.JSONDecodeError) as e:
            logging.error(f"Error loading state from {self.state_file}: {e}")
            return {}
