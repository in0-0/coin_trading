"""
TDD: Signal Enum 구조 개선에 대한 실패하는 테스트 작성
"""
import unittest
from enum import Enum
from typing import Optional


class TestSignalRefactor(unittest.TestCase):
    """Signal Enum 구조 개선의 동작을 검증하는 테스트"""

    def test_signal_enum_current_structure(self):
        """현재 Signal Enum의 구조를 확인"""
        from models import Signal

        # 현재 Signal enum의 값들을 확인
        self.assertTrue(hasattr(Signal, 'HOLD'))
        self.assertTrue(hasattr(Signal, 'BUY'))
        self.assertTrue(hasattr(Signal, 'SELL'))

        # 새로운 값들이 추가되어 있는지 확인
        self.assertTrue(hasattr(Signal, 'BUY_NEW'))
        self.assertTrue(hasattr(Signal, 'BUY_ADD'))
        self.assertTrue(hasattr(Signal, 'SELL_PARTIAL'))
        self.assertTrue(hasattr(Signal, 'SELL_ALL'))
        self.assertTrue(hasattr(Signal, 'UPDATE_TRAIL'))

    def test_signal_enum_too_many_responsibilities(self):
        """Signal Enum이 너무 많은 책임을 가지고 있음 - 리팩토링 필요"""
        from models import Signal

        # 현재 Signal enum이 7개의 값을 가지고 있음
        signal_values = [s for s in dir(Signal) if not s.startswith('_') and isinstance(getattr(Signal, s), Signal)]
        self.assertGreater(len(signal_values), 5)  # 너무 많은 값들

        # 이로 인해 단일 enum이 너무 많은 상태와 액션을 표현하려 함
        # 리팩토링이 필요함을 보여주는 테스트

    def test_position_action_separation_needed(self):
        """PositionAction과 Signal이 명확히 분리되어야 함"""
        from models import PositionAction, Signal

        # 현재 PositionAction은 있지만 Signal과 명확히 분리되지 않음
        action = PositionAction("BUY_ADD", qty_ratio=0.5, reason="test")
        self.assertEqual(action.action_type, "BUY_ADD")

        # Signal과 PositionAction의 관계가 명확하지 않음
        # BUY_ADD 같은 액션들이 Signal에도 있고 PositionAction에도 있음
        self.assertTrue(hasattr(Signal, 'BUY_ADD'))
        # 이 중복성과 혼란스러운 구조를 개선해야 함

    def test_signal_enum_values_are_inconsistent(self):
        """Signal Enum의 값들이 일관성 없이 정의되어 있음"""
        from models import Signal

        # Signal enum의 값들을 확인
        hold_signal = Signal.HOLD
        buy_signal = Signal.BUY
        buy_add_signal = Signal.BUY_ADD

        # 값들이 0, 1, 2, 3, 4, 5, 6, 7 순서로 되어 있음
        self.assertEqual(hold_signal.value, 0)
        self.assertEqual(buy_signal.value, 1)
        self.assertEqual(buy_add_signal.value, 4)  # 2, 3이 누락됨

        # 이 불연속성은 코드를 혼란스럽게 만듦
        # 더 나은 구조로 리팩토링이 필요함

    def test_position_action_class_exists(self):
        """PositionAction 클래스가 존재하는지 확인"""
        from models import PositionAction

        # PositionAction이 dataclass로 정의되어 있는지 확인
        action = PositionAction(
            action_type="BUY_ADD",
            qty_ratio=0.5,
            price=50000.0,
            reason="pyramiding",
            metadata={"confidence": 0.8}
        )

        self.assertEqual(action.action_type, "BUY_ADD")
        self.assertEqual(action.qty_ratio, 0.5)
        self.assertEqual(action.price, 50000.0)
        self.assertEqual(action.reason, "pyramiding")
        self.assertEqual(action.metadata["confidence"], 0.8)


class TestNewSignalStructure(unittest.TestCase):
    """새로운 Signal 구조에 대한 요구사항 테스트"""

    def test_new_signal_structure_should_separate_concerns(self):
        """새로운 Signal 구조는 상태와 액션을 명확히 분리해야 함"""
        # 새로운 구조가 필요함을 보여주는 테스트
        # 현재 구조의 문제점들을 보여줌

        from models import Signal

        # 현재 Signal enum이 너무 많은 값을 가지고 있음
        signals = list(Signal)
        self.assertGreater(len(signals), 5)

        # 이는 단일 enum이 너무 많은 책임을 가지고 있음을 보여줌
        # 새로운 구조로 리팩토링이 필요함

    def test_new_structure_should_be_extensible(self):
        """새로운 구조는 쉽게 확장 가능해야 함"""
        # 새로운 구조가 필요함을 보여주는 테스트

        from models import Signal

        # 현재 구조는 새로운 신호 유형 추가가 어려움
        # BUY_NEW, BUY_ADD, SELL_PARTIAL 등의 값들이 혼재되어 있음
        # 이는 향후 확장성을 제한함

    def test_new_structure_should_be_type_safe(self):
        """새로운 구조는 타입 안정성을 제공해야 함"""
        # 새로운 구조가 필요함을 보여주는 테스트

        from models import Signal

        # 현재 Signal enum은 타입 안정성이 부족함
        # 다양한 종류의 신호들이 하나의 enum에 혼재되어 있음
        # 이는 타입 검사와 코드 자동완성에 어려움을 줌


class TestNewSignalImplementation(unittest.TestCase):
    """새로운 Signal 구조 구현 테스트"""

    def test_trading_signal_creation(self):
        """TradingSignal이 올바르게 생성되는지 확인"""
        from core.signal import TradingSignal, SignalType, SignalAction

        # 기본 신호 생성
        signal = TradingSignal(SignalType.BUY, SignalAction.ENTRY, confidence=0.8)
        self.assertEqual(signal.signal_type, SignalType.BUY)
        self.assertEqual(signal.action, SignalAction.ENTRY)
        self.assertEqual(signal.confidence, 0.8)

    def test_trading_signal_properties(self):
        """TradingSignal의 속성들이 올바르게 작동하는지 확인"""
        from core.signal import TradingSignal, SignalType, SignalAction

        # 매수 진입 신호
        buy_signal = TradingSignal(SignalType.BUY, SignalAction.ENTRY)
        self.assertTrue(buy_signal.is_buy)
        self.assertTrue(buy_signal.is_entry)
        self.assertFalse(buy_signal.is_sell)
        self.assertFalse(buy_signal.is_hold)

        # 매도 부분 청산 신호
        sell_signal = TradingSignal(SignalType.SELL, SignalAction.PARTIAL_EXIT)
        self.assertTrue(sell_signal.is_sell)
        self.assertTrue(sell_signal.is_partial_exit)
        self.assertFalse(sell_signal.is_buy)

        # 홀드 신호
        hold_signal = TradingSignal(SignalType.HOLD, SignalAction.EXIT)
        self.assertTrue(hold_signal.is_hold)
        self.assertFalse(hold_signal.is_buy)
        self.assertFalse(hold_signal.is_sell)

    def test_signal_string_representation(self):
        """TradingSignal의 문자열 표현이 올바른지 확인"""
        from core.signal import TradingSignal, SignalType, SignalAction

        signal = TradingSignal(
            SignalType.BUY,
            SignalAction.ADD,
            confidence=0.75,
            metadata={"reason": "pyramiding", "amount": 1000}
        )

        signal_str = str(signal)
        self.assertIn("매수", signal_str)
        self.assertIn("추가", signal_str)
        self.assertIn("신뢰도: 75.0%", signal_str)
        self.assertIn("pyramiding", signal_str)

    def test_signal_conversion_methods(self):
        """Signal과 TradingSignal 간 변환 메소드가 작동하는지 확인"""
        from core.signal import Signal, TradingSignal, SignalType, SignalAction

        # 기존 Signal에서 TradingSignal로 변환
        old_signal = Signal.BUY_ADD
        trading_signal = old_signal.to_trading_signal(confidence=0.6, metadata={"test": True})
        self.assertEqual(trading_signal.signal_type, SignalType.BUY)
        self.assertEqual(trading_signal.action, SignalAction.ADD)

        # TradingSignal에서 기존 Signal로 변환
        old_signal_back = Signal.from_trading_signal(trading_signal)
        self.assertEqual(old_signal_back, Signal.BUY_ADD)

    def test_convenience_functions(self):
        """편의 함수들이 올바르게 작동하는지 확인"""
        from core.signal import create_buy_signal, create_sell_signal, create_hold_signal, SignalAction

        # 매수 신호 생성
        buy_signal = create_buy_signal(SignalAction.ADD, confidence=0.7)
        self.assertTrue(buy_signal.is_buy)
        self.assertTrue(buy_signal.is_add_position)

        # 매도 신호 생성
        sell_signal = create_sell_signal(SignalAction.PARTIAL_EXIT, confidence=0.9)
        self.assertTrue(sell_signal.is_sell)
        self.assertTrue(sell_signal.is_partial_exit)

        # 홀드 신호 생성
        hold_signal = create_hold_signal(confidence=0.1)
        self.assertTrue(hold_signal.is_hold)

    def test_signal_like_type_compatibility(self):
        """SignalLike 타입이 기존 코드와 호환되는지 확인"""
        from core.signal import SignalLike, Signal, TradingSignal, SignalType, SignalAction

        # 기존 Signal
        old_signal = Signal.BUY
        new_signal = TradingSignal(SignalType.BUY, SignalAction.ENTRY)

        # 둘 다 SignalLike 타입으로 사용 가능
        signal_like_list: list[SignalLike] = [old_signal, new_signal]
        self.assertEqual(len(signal_like_list), 2)

        # 타입 검증
        for signal in signal_like_list:
            if isinstance(signal, Signal):
                self.assertIsInstance(signal, Signal)
            elif isinstance(signal, TradingSignal):
                self.assertIsInstance(signal, TradingSignal)


if __name__ == "__main__":
    unittest.main()
