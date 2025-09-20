"""
TDD: 커스텀 예외 클래스에 대한 실패하는 테스트 작성
"""
import unittest
from datetime import datetime


class TestCustomExceptions(unittest.TestCase):
    """커스텀 예외 클래스의 동작을 검증하는 테스트"""

    def test_exceptions_module_exists(self):
        """Exceptions 모듈이 존재하는지 확인"""
        from core.exceptions import TradingError, OrderError, ConfigurationError
        self.assertTrue(issubclass(TradingError, Exception))
        self.assertTrue(issubclass(OrderError, TradingError))
        self.assertTrue(issubclass(ConfigurationError, TradingError))

    def test_trading_error_should_be_base_exception(self):
        """TradingError는 BaseException의 서브클래스여야 함"""
        try:
            from core.exceptions import TradingError

            # TradingError가 BaseException을 상속하는지 확인
            error = TradingError("Test trading error")
            self.assertIsInstance(error, BaseException)
            self.assertTrue(issubclass(TradingError, BaseException))

            # 메시지가 올바르게 설정되는지 확인 (타임스탬프 포함)
            error_str = str(error)
            self.assertIn("Test trading error", error_str)
            self.assertIn("[", error_str)  # 타임스탬프 포함 확인

            # 타임스탬프가 포함되는지 확인
            self.assertTrue(hasattr(error, 'timestamp'))
            self.assertIsInstance(error.timestamp, datetime)

        except ImportError:
            self.fail("TradingError 클래스가 존재하지 않습니다")

    def test_order_error_should_inherit_trading_error(self):
        """OrderError는 TradingError를 상속해야 함"""
        try:
            from core.exceptions import TradingError, OrderError

            # OrderError가 TradingError를 상속하는지 확인
            self.assertTrue(issubclass(OrderError, TradingError))

            # OrderError 인스턴스 생성
            error = OrderError("Test order error", symbol="BTCUSDT", order_id="12345")
            self.assertIsInstance(error, TradingError)

            # 추가 속성들이 올바르게 설정되는지 확인
            self.assertEqual(error.symbol, "BTCUSDT")
            self.assertEqual(error.order_id, "12345")

        except ImportError:
            self.fail("OrderError 클래스가 존재하지 않습니다")

    def test_configuration_error_should_inherit_trading_error(self):
        """ConfigurationError는 TradingError를 상속해야 함"""
        try:
            from core.exceptions import TradingError, ConfigurationError

            # ConfigurationError가 TradingError를 상속하는지 확인
            self.assertTrue(issubclass(ConfigurationError, TradingError))

            # ConfigurationError 인스턴스 생성
            error = ConfigurationError("Test configuration error", config_key="RISK_PER_TRADE")
            self.assertIsInstance(error, TradingError)

            # 추가 속성들이 올바르게 설정되는지 확인
            self.assertEqual(error.config_key, "RISK_PER_TRADE")

        except ImportError:
            self.fail("ConfigurationError 클래스가 존재하지 않습니다")

    def test_exception_context_information(self):
        """예외들은 충분한 컨텍스트 정보를 제공해야 함"""
        try:
            from core.exceptions import TradingError, OrderError, ConfigurationError

            # TradingError 컨텍스트
            trading_error = TradingError("Network timeout", context={"retry_count": 3})
            self.assertEqual(trading_error.context["retry_count"], 3)

            # OrderError 컨텍스트
            order_error = OrderError(
                "Invalid order quantity",
                symbol="ETHUSDT",
                order_id="67890",
                context={"requested_qty": 100, "min_qty": 10}
            )
            self.assertEqual(order_error.symbol, "ETHUSDT")
            self.assertEqual(order_error.context["requested_qty"], 100)

            # ConfigurationError 컨텍스트
            config_error = ConfigurationError(
                "Invalid risk percentage",
                config_key="RISK_PER_TRADE",
                context={"value": 1.5, "max_value": 1.0}
            )
            self.assertEqual(config_error.config_key, "RISK_PER_TRADE")
            self.assertEqual(config_error.context["value"], 1.5)

        except ImportError:
            self.fail("예외 클래스들이 존재하지 않습니다")


if __name__ == "__main__":
    unittest.main()
