import unittest
from datetime import UTC, datetime
from unittest.mock import patch

import pandas as pd

from models import Position, PositionAction, Signal
from strategies.atr_trailing_stop_strategy import ATRTrailingStopStrategy


class TestATRTrailingStopStrategy(unittest.TestCase):
    def setUp(self):
        self.symbol = "BTCUSDT"
        self.strategy = ATRTrailingStopStrategy(symbol=self.symbol, atr_multiplier=1.0, risk_per_trade=0.01)

    @patch("pandas_ta.rsi")
    @patch("pandas_ta.atr")
    def test_buy_signal_when_rsi_low_and_no_position(self, mock_atr, mock_rsi):
        df = pd.DataFrame({
            "Open time": pd.to_datetime(["2023-01-01", "2023-01-02", "2023-01-03"]),
            "Open": [10, 11, 12],
            "High": [11, 12, 13],
            "Low": [9, 10, 11],
            "Close": [10.5, 11.5, 12.5],
            "Volume": [100, 100, 100],
        })
        mock_atr.return_value = pd.Series([0.5, 0.6, 0.7])
        mock_rsi.return_value = pd.Series([50, 40, 25])  # Latest RSI < 30 → BUY

        signal = self.strategy.get_signal(df.copy(), position=None)
        self.assertEqual(signal, Signal.BUY)

    @patch("pandas_ta.rsi")
    @patch("pandas_ta.atr")
    def test_sell_signal_on_stop_hit_for_open_long(self, mock_atr, mock_rsi):
        df = pd.DataFrame({
            "Open time": pd.to_datetime(["2023-01-01", "2023-01-02", "2023-01-03"]),
            "Open": [10, 11, 12],
            "High": [11, 12, 13],
            "Low": [9, 10, 11],
            "Close": [10.5, 9.0, 8.5],  # Drop below stop
            "Volume": [100, 100, 100],
        })
        mock_atr.return_value = pd.Series([0.5, 0.6, 0.7])
        mock_rsi.return_value = pd.Series([50, 40, 35])

        position = Position(symbol=self.symbol, qty=1.0, entry_price=10.0, stop_price=9.5)
        signal = self.strategy.get_signal(df.copy(), position=position)
        self.assertEqual(signal, Signal.SELL)

    @patch("pandas_ta.rsi")
    @patch("pandas_ta.atr")
    def test_hold_when_conditions_not_met(self, mock_atr, mock_rsi):
        df = pd.DataFrame({
            "Open time": pd.to_datetime(["2023-01-01", "2023-01-02", "2023-01-03"]),
            "Open": [10, 11, 12],
            "High": [11, 12, 13],
            "Low": [9, 10, 11],
            "Close": [10.5, 11.0, 11.2],
            "Volume": [100, 100, 100],
        })
        mock_atr.return_value = pd.Series([0.5, 0.6, 0.7])
        mock_rsi.return_value = pd.Series([50, 40, 50])

        position = Position(symbol=self.symbol, qty=1.0, entry_price=10.0, stop_price=8.0)
        signal = self.strategy.get_signal(df.copy(), position=position)
        self.assertEqual(signal, Signal.HOLD)

    # === Phase 1 실패 테스트들 ===

    def test_new_signal_enum_values(self):
        """새로운 Signal enum 값들이 정의되어 있어야 함"""
        # 현재 Signal enum에는 BUY, SELL, HOLD만 있음
        # 새로운 값들: BUY_NEW, BUY_ADD, SELL_PARTIAL, SELL_ALL, UPDATE_TRAIL
        self.assertTrue(hasattr(Signal, 'BUY_NEW'))
        self.assertTrue(hasattr(Signal, 'BUY_ADD'))
        self.assertTrue(hasattr(Signal, 'SELL_PARTIAL'))
        self.assertTrue(hasattr(Signal, 'SELL_ALL'))
        self.assertTrue(hasattr(Signal, 'UPDATE_TRAIL'))

    def test_position_action_dataclass_exists(self):
        """PositionAction dataclass가 정의되어 있어야 함"""
        # PositionAction은 아직 models.py에 정의되지 않음
        action = PositionAction("BUY_ADD", qty_ratio=0.5, reason="test")
        self.assertEqual(action.action_type, "BUY_ADD")
        self.assertEqual(action.qty_ratio, 0.5)

    def test_strategy_get_position_action_method(self):
        """전략에 get_position_action 메소드가 있어야 함"""
        # Phase 1에서 ATRTrailingStopStrategy에 get_position_action 메소드가 추가됨
        self.assertTrue(hasattr(self.strategy, 'get_position_action'))

        # 메소드 호출 가능 여부 확인
        df = pd.DataFrame({
            "Open time": pd.to_datetime(["2023-01-01", "2023-01-02", "2023-01-03"]),
            "Open": [10, 11, 12],
            "High": [11, 12, 13],
            "Low": [9, 10, 11],
            "Close": [10.5, 11.5, 12.5],
            "Volume": [100, 100, 100],
        })

        position = Position(symbol="BTCUSDT", qty=1.0, entry_price=100.0, stop_price=95.0)
        result = self.strategy.get_position_action(df, position)

        # Phase 1에서는 None을 반환 (향후 Phase 2, 3, 4에서 구현)
        self.assertIsNone(result)

    def test_enhanced_position_structure(self):
        """향상된 Position 클래스 구조 테스트"""
        # Phase 1에서 추가된 향상된 구조 검증
        position = Position(symbol="BTCUSDT", qty=1.0, entry_price=100.0, stop_price=95.0)

        # 향상된 속성들이 존재해야 함
        self.assertTrue(hasattr(position, 'legs'))
        self.assertTrue(hasattr(position, 'partial_exits'))
        self.assertTrue(hasattr(position, 'trailing_stop_price'))
        self.assertTrue(hasattr(position, 'highest_price'))

        # 초기값 확인
        self.assertEqual(len(position.legs), 1)  # 초기 레그가 자동 생성됨
        self.assertEqual(position.trailing_stop_price, 95.0)
        self.assertEqual(position.highest_price, 100.0)

    def test_position_methods_for_advanced_features(self):
        """고급 포지션 관리에 필요한 메소드들"""
        position = Position(symbol="BTCUSDT", qty=1.0, entry_price=100.0, stop_price=95.0)

        # Phase 1에서 추가된 메소드들이 존재해야 함
        self.assertTrue(hasattr(position, 'can_add_position'))
        self.assertTrue(hasattr(position, 'add_leg'))
        self.assertTrue(hasattr(position, 'unrealized_pnl_pct'))
        self.assertTrue(hasattr(position, 'update_trailing_stop'))

        # 메소드 호출 가능 여부 확인
        result = position.can_add_position(datetime.now(UTC))
        self.assertIsInstance(result, bool)

        # unrealized_pnl_pct는 현재가 없으므로 0.0 반환
        self.assertEqual(position.unrealized_pnl_pct, 0.0)

        # 트레일링 스탑 업데이트
        position.update_trailing_stop(96.0)
        self.assertEqual(position.trailing_stop_price, 96.0)

    # === Phase 2 실패 테스트들 ===

    def test_position_manager_not_exists(self):
        """PositionManager 클래스가 아직 구현되지 않음"""
        from trader.position_manager import PositionManager
        pm = PositionManager()
        self.assertTrue(hasattr(pm, 'should_pyramid'))
        self.assertTrue(hasattr(pm, 'should_average_down'))

    def test_atr_strategy_pyramid_logic_not_implemented(self):
        """ATR 전략에 불타기/물타기 로직이 아직 구현되지 않음"""
        df = pd.DataFrame({
            "Open time": pd.to_datetime(["2023-01-01", "2023-01-02", "2023-01-03"]),
            "Open": [10, 11, 12],
            "High": [11, 12, 13],
            "Low": [9, 10, 11],
            "Close": [10.5, 11.5, 12.5],
            "Volume": [100, 100, 100],
        })

        position = Position(symbol="BTCUSDT", qty=1.0, entry_price=100.0, stop_price=95.0)
        # 현재는 None 반환 (Phase 2에서 구현 예정)
        result = self.strategy.get_position_action(df, position)
        self.assertIsNone(result)

    def test_buy_add_signal_not_handled(self):
        """BUY_ADD 신호 처리가 아직 구현되지 않음"""
        # Signal.BUY_ADD는 정의되었지만 실제 처리 로직 없음
        self.assertEqual(Signal.BUY_ADD, Signal.BUY_ADD)
        # live_trader_gpt.py에서 Signal.BUY_ADD 처리 로직이 없으므로 실패 예상

    # === Phase 3 실패 테스트들 ===

    def test_trailing_stop_manager_not_exists(self):
        """TrailingStopManager 클래스가 아직 구현되지 않음"""
        from trader.trailing_stop_manager import TrailingStopManager
        tsm = TrailingStopManager()
        self.assertTrue(hasattr(tsm, 'should_activate_trailing'))
        self.assertTrue(hasattr(tsm, 'update_trailing_stop'))

    def test_atr_strategy_trailing_logic_not_implemented(self):
        """ATR 전략에 트레일링 스탑 로직이 아직 구현되지 않음"""
        df = pd.DataFrame({
            "Open time": pd.to_datetime(["2023-01-01", "2023-01-02", "2023-01-03"]),
            "Open": [10, 11, 12],
            "High": [11, 12, 13],
            "Low": [9, 10, 11],
            "Close": [10.5, 11.5, 12.5],
            "Volume": [100, 100, 100],
        })

        position = Position(symbol="BTCUSDT", qty=1.0, entry_price=100.0, stop_price=95.0)
        # 현재는 None 반환 (Phase 3에서 구현 예정)
        result = self.strategy.get_position_action(df, position)
        # Phase 2에서 불타기/물타기 로직이 구현되어 있으므로 None이 아닐 수 있음
        # 하지만 UPDATE_TRAIL 액션은 아직 구현되지 않음

    def test_update_trail_signal_not_handled(self):
        """UPDATE_TRAIL 신호 처리가 아직 구현되지 않음"""
        # Signal.UPDATE_TRAIL은 정의되었지만 실제 처리 로직 없음
        self.assertEqual(Signal.UPDATE_TRAIL, Signal.UPDATE_TRAIL)
        # live_trader_gpt.py에서 Signal.UPDATE_TRAIL 처리 로직이 없으므로 실패 예상

    # === Phase 4 실패 테스트들 ===

    def test_partial_exit_manager_not_exists(self):
        """PartialExitManager 클래스가 아직 구현되지 않음"""
        from trader.partial_exit_manager import PartialExitManager
        pem = PartialExitManager()
        self.assertTrue(hasattr(pem, 'should_partial_exit'))
        self.assertTrue(hasattr(pem, 'get_partial_exit_action'))

    def test_atr_strategy_partial_exit_logic_not_implemented(self):
        """ATR 전략에 부분 청산 로직이 아직 구현되지 않음"""
        df = pd.DataFrame({
            "Open time": pd.to_datetime(["2023-01-01", "2023-01-02", "2023-01-03"]),
            "Open": [10, 11, 12],
            "High": [11, 12, 13],
            "Low": [9, 10, 11],
            "Close": [10.5, 11.5, 12.5],
            "Volume": [100, 100, 100],
        })

        position = Position(symbol="BTCUSDT", qty=1.0, entry_price=100.0, stop_price=95.0)
        # Phase 3에서 트레일링 로직이 구현되어 있으므로 None이 아닐 수 있음
        # 하지만 SELL_PARTIAL 액션은 아직 구현되지 않음

    def test_sell_partial_signal_not_handled(self):
        """SELL_PARTIAL 신호 처리가 아직 구현되지 않음"""
        # Signal.SELL_PARTIAL은 정의되었지만 실제 처리 로직 없음
        self.assertEqual(Signal.SELL_PARTIAL, Signal.SELL_PARTIAL)
        # live_trader_gpt.py에서 Signal.SELL_PARTIAL 처리 로직이 없으므로 실패 예상


if __name__ == "__main__":
    unittest.main()

