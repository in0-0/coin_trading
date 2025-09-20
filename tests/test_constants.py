"""
TDD: 상수 정의 파일에 대한 실패하는 테스트 작성
"""
import unittest


class TestConstants(unittest.TestCase):
    """상수 정의 파일의 동작을 검증하는 테스트"""

    def test_constants_file_exists(self):
        """Constants 파일이 존재하는지 확인"""
        from core.constants import TradingConstants
        self.assertTrue(issubclass(TradingConstants, object))

    def test_constants_should_provide_trading_values(self):
        """Constants 클래스는 거래 관련 상수들을 제공해야 함"""
        # 이 테스트는 Constants 클래스가 없으므로 실패할 것임
        try:
            from core.constants import TradingConstants

            # ATR 관련 상수들
            self.assertTrue(hasattr(TradingConstants, 'DEFAULT_ATR_PERIOD'))
            self.assertEqual(TradingConstants.DEFAULT_ATR_PERIOD, 14)

            self.assertTrue(hasattr(TradingConstants, 'DEFAULT_ATR_MULTIPLIER'))
            self.assertEqual(TradingConstants.DEFAULT_ATR_MULTIPLIER, 0.5)

            # 리스크 관리 상수들
            self.assertTrue(hasattr(TradingConstants, 'DEFAULT_RISK_PER_TRADE'))
            self.assertEqual(TradingConstants.DEFAULT_RISK_PER_TRADE, 0.005)

            # 주문 설정 상수들
            self.assertTrue(hasattr(TradingConstants, 'DEFAULT_MAX_SLIPPAGE_BPS'))
            self.assertEqual(TradingConstants.DEFAULT_MAX_SLIPPAGE_BPS, 50)

            self.assertTrue(hasattr(TradingConstants, 'DEFAULT_ORDER_TIMEOUT_SEC'))
            self.assertEqual(TradingConstants.DEFAULT_ORDER_TIMEOUT_SEC, 10)

            self.assertTrue(hasattr(TradingConstants, 'DEFAULT_ORDER_RETRY'))
            self.assertEqual(TradingConstants.DEFAULT_ORDER_RETRY, 3)

        except ImportError:
            self.fail("Constants 클래스가 존재하지 않습니다")

    def test_constants_should_provide_bracket_settings(self):
        """Constants 클래스는 브래킷 주문 관련 상수들을 제공해야 함"""
        try:
            from core.constants import TradingConstants

            # Bracket 주문 상수들
            self.assertTrue(hasattr(TradingConstants, 'DEFAULT_BRACKET_K_SL'))
            self.assertEqual(TradingConstants.DEFAULT_BRACKET_K_SL, 1.5)

            self.assertTrue(hasattr(TradingConstants, 'DEFAULT_BRACKET_RR'))
            self.assertEqual(TradingConstants.DEFAULT_BRACKET_RR, 2.0)

        except ImportError:
            self.fail("Constants 클래스가 존재하지 않습니다")

    def test_constants_should_provide_position_limits(self):
        """Constants 클래스는 포지션 제한 관련 상수들을 제공해야 함"""
        try:
            from core.constants import TradingConstants

            # 포지션 제한 상수들
            self.assertTrue(hasattr(TradingConstants, 'DEFAULT_MAX_CONCURRENT_POSITIONS'))
            self.assertEqual(TradingConstants.DEFAULT_MAX_CONCURRENT_POSITIONS, 3)

            self.assertTrue(hasattr(TradingConstants, 'DEFAULT_MAX_SYMBOL_WEIGHT'))
            self.assertEqual(TradingConstants.DEFAULT_MAX_SYMBOL_WEIGHT, 0.20)

            self.assertTrue(hasattr(TradingConstants, 'DEFAULT_MIN_ORDER_USDT'))
            self.assertEqual(TradingConstants.DEFAULT_MIN_ORDER_USDT, 10.0)

        except ImportError:
            self.fail("Constants 클래스가 존재하지 않습니다")


if __name__ == "__main__":
    unittest.main()
