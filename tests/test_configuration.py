"""
TDD: Configuration 클래스에 대한 실패하는 테스트 작성
"""
import unittest
from unittest.mock import patch, MagicMock

from core.configuration import Configuration


class TestConfiguration(unittest.TestCase):
    """Configuration 클래스의 동작을 검증하는 테스트"""

    def test_configuration_class_exists(self):
        """Configuration 클래스가 존재하는지 확인"""
        from core.configuration import Configuration
        self.assertTrue(issubclass(Configuration, object))

    def test_configuration_should_load_env_vars(self):
        """Configuration 클래스는 환경변수들을 로드해야 함"""
        # 이 테스트는 Configuration 클래스가 없으므로 실패할 것임
        try:
            config = Configuration()
            # 기본 설정들이 올바르게 로드되는지 확인
            self.assertIsInstance(config.symbols, list)
            self.assertIsInstance(config.execution_interval, int)
            self.assertIsInstance(config.risk_per_trade, float)
        except ImportError:
            self.fail("Configuration 클래스가 존재하지 않습니다")

    def test_configuration_should_validate_settings(self):
        """Configuration 클래스는 설정 값들의 유효성을 검증해야 함"""
        # 이 테스트는 Configuration 클래스가 없으므로 실패할 것임
        try:
            config = Configuration()

            # 설정들이 유효한 범위 내에 있는지 확인
            self.assertGreater(config.risk_per_trade, 0.0)
            self.assertLess(config.risk_per_trade, 1.0)
            self.assertGreater(config.execution_interval, 0)

        except ImportError:
            self.fail("Configuration 클래스가 존재하지 않습니다")

    def test_configuration_should_provide_constants(self):
        """Configuration 클래스는 상수들을 제공해야 함"""
        # 이 테스트는 Configuration 클래스가 없으므로 실패할 것임
        try:
            config = Configuration()

            # 매직 넘버들을 상수로 제공하는지 확인
            self.assertTrue(hasattr(config, 'DEFAULT_ATR_PERIOD'))
            self.assertTrue(hasattr(config, 'DEFAULT_ATR_MULTIPLIER'))
            self.assertEqual(config.DEFAULT_ATR_PERIOD, 14)
            self.assertEqual(config.DEFAULT_ATR_MULTIPLIER, 0.5)

        except ImportError:
            self.fail("Configuration 클래스가 존재하지 않습니다")


if __name__ == "__main__":
    unittest.main()
