import os
import json
import unittest
from state_manager import StateManager


class TestStateManager(unittest.TestCase):
    def setUp(self):
        """테스트 실행 전 테스트용 상태 파일을 준비합니다."""
        self.test_file = "test_state.json"
        self.state_manager = StateManager(state_file=self.test_file)
        # 테스트 전에 혹시 파일이 남아있으면 삭제
        if os.path.exists(self.test_file):
            os.remove(self.test_file)

    def tearDown(self):
        """테스트 실행 후 테스트용 상태 파일을 삭제합니다."""
        if os.path.exists(self.test_file):
            os.remove(self.test_file)

    def test_load_state_no_file(self):
        """상태 파일이 없을 때 기본 상태를 반환하는지 테스트합니다."""
        state = self.state_manager.load_state()
        self.assertEqual(
            state, {"in_position": False, "position_size": 0.0, "cash": 10000.0}
        )

    def test_save_and_load_state(self):
        """상태를 저장하고 다시 올바르게 불러오는지 테스트합니다."""
        state_to_save = {"in_position": True, "position_size": 0.1, "cash": 5000.0}
        self.state_manager.save_state(state_to_save)

        # 파일이 실제로 생성되었는지 확인
        self.assertTrue(os.path.exists(self.test_file))

        # 파일 내용을 직접 읽어 확인
        with open(self.test_file, "r") as f:
            saved_data = json.load(f)
        self.assertEqual(saved_data, state_to_save)

        # load_state 메소드를 통해 확인
        loaded_state = self.state_manager.load_state()
        self.assertEqual(loaded_state, state_to_save)

    def test_load_state_corrupted_file(self):
        """손상된 JSON 파일을 읽으려 할 때 기본 상태를 반환하는지 테스트합니다."""
        with open(self.test_file, "w") as f:
            f.write("{'in_position': True,")  # 일부러 잘못된 JSON 형식으로 저장

        state = self.state_manager.load_state()
        self.assertEqual(
            state, {"in_position": False, "position_size": 0.0, "cash": 10000.0}
        )


if __name__ == "__main__":
    unittest.main()
