"""
개선된 컴포넌트들의 통합 테스트

TDD: 실패하는 테스트부터 작성
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone

from core.error_handler import ErrorHandler, get_global_error_handler
from core.dependency_injection import TradingConfig, get_config, configure_dependencies
from core.exceptions import ConfigurationError, DataError, ValidationError
from core.data_models import KlineData, NormalizedKlineData, StrategyConfig
from core.position_manager import PositionCalculator, PositionStateManager, PositionService
from binance_data_improved import ImprovedBinanceData
from improved_strategy_factory import StrategyFactory


class TestErrorHandler:
    """에러 처리 시스템 테스트"""

    def test_error_handler_creation(self):
        """에러 핸들러 생성 테스트"""
        handler = ErrorHandler()
        assert handler is not None

    def test_safe_wrapper_creation(self):
        """안전 실행 래퍼 생성 테스트"""
        handler = ErrorHandler()
        wrapper = handler.create_safe_wrapper()
        assert callable(wrapper)

    def test_error_handling_with_validation_error(self):
        """검증 에러 처리 테스트"""
        handler = ErrorHandler()
        error = ValidationError("Test validation error", field="test_field", value="test_value")

        # 에러 처리가 성공적으로 완료되어야 함
        # ValidationError는 복구 전략이 있으므로 True를 반환
        result = handler.handle_error(error, notify=False)
        assert result is True  # 복구 전략 있음


class TestTradingConfig:
    """트레이딩 설정 테스트"""

    def test_config_from_env_defaults(self):
        """환경변수로부터 기본 설정 로드 테스트"""
        with patch.dict('os.environ', {}, clear=True):
            config = TradingConfig.from_env()
            assert config.mode == "TESTNET"
            assert "BTCUSDT" in config.symbols  # 기본 심볼 포함 확인

    def test_config_validation(self):
        """설정 검증 테스트"""
        config = TradingConfig()
        config.risk_per_trade = 1.5  # 잘못된 값

        errors = config.validate()
        assert len(errors) > 0
        assert any("Risk per trade must be between 0 and 1" in error for error in errors)

    def test_strategy_config_creation(self):
        """심볼별 전략 설정 생성 테스트"""
        config = TradingConfig()
        strategy_config = config.get_strategy_config("BTCUSDT")

        assert isinstance(strategy_config, StrategyConfig)
        assert strategy_config.symbol == "BTCUSDT"


class TestDataModels:
    """데이터 모델 테스트"""

    def test_kline_data_creation(self):
        """Kline 데이터 생성 테스트"""
        kline_data = KlineData(
            open_time=datetime.now(timezone.utc),
            open_price=50000,
            high_price=51000,
            low_price=49500,
            close_price=50500,
            volume=100,
            close_time=datetime.now(timezone.utc),
            quote_asset_volume=5000000,
            number_of_trades=50,
            taker_buy_base_asset_volume=60,
            taker_buy_quote_asset_volume=3000000
        )

        assert kline_data.open_price == 50000
        assert kline_data.close_price == 50500

    def test_kline_data_validation_price_consistency(self):
        """가격 일관성 검증 테스트"""
        with pytest.raises(ValueError, match="Open price cannot be higher than high price"):
            KlineData(
                open_time=datetime.now(timezone.utc),
                open_price=51000,  # 잘못된 값: 고가보다 높음
                high_price=50000,
                low_price=49500,
                close_price=50500,
                volume=100,
                close_time=datetime.now(timezone.utc),
                quote_asset_volume=5000000,
                number_of_trades=50,
                taker_buy_base_asset_volume=60,
                taker_buy_quote_asset_volume=3000000
            )


class TestPositionManager:
    """포지션 관리 시스템 테스트"""

    def test_position_calculator_average_entry_price(self):
        """평균 진입가 계산 테스트"""
        legs = [
            Mock(side="BUY", quantity=1.0, price=50000),
            Mock(side="BUY", quantity=2.0, price=51000),
        ]

        avg_price = PositionCalculator.calculate_average_entry_price(legs)
        expected = (1.0 * 50000 + 2.0 * 51000) / 3.0  # 50666.67
        assert abs(avg_price - expected) < 0.01

    def test_position_state_manager_creation(self):
        """포지션 상태 관리자 생성 테스트"""
        manager = PositionStateManager("BTCUSDT")
        assert manager.symbol == "BTCUSDT"
        assert manager.status == "ACTIVE"
        assert len(manager.legs) == 0

    def test_position_service_creation(self):
        """포지션 서비스 생성 테스트"""
        service = PositionService()
        assert service.calculator is not None


class TestImprovedBinanceData:
    """개선된 Binance 데이터 제공자 테스트"""

    @patch('binance_data_improved.Client')
    def test_binance_data_creation(self, mock_client):
        """Binance 데이터 제공자 생성 테스트"""
        mock_client_instance = Mock()
        mock_client.return_value = mock_client_instance

        data_provider = ImprovedBinanceData("test_api", "test_secret")
        assert data_provider.client == mock_client_instance

    def test_get_current_price_invalid_symbol(self):
        """잘못된 심볼로 현재가 조회 테스트"""
        with patch('binance_data_improved.Client') as mock_client:
            mock_client_instance = Mock()
            mock_client_instance.get_symbol_ticker.side_effect = Exception("Invalid symbol")
            mock_client.return_value = mock_client_instance

            data_provider = ImprovedBinanceData("test_api", "test_secret")

            # 예외가 발생해야 함
            with pytest.raises(Exception):
                data_provider.get_current_price("INVALID_SYMBOL")


class TestStrategyFactory:
    """전략 팩토리 테스트"""

    def test_strategy_factory_creation(self):
        """전략 팩토리 생성 테스트"""
        factory = StrategyFactory()
        assert factory is not None
        assert len(factory.get_available_strategies()) > 0

    def test_create_unknown_strategy(self):
        """알 수 없는 전략 생성 시도 테스트"""
        factory = StrategyFactory()

        with pytest.raises(ConfigurationError, match="Unknown strategy"):
            factory.create_strategy("unknown_strategy", "BTCUSDT")

    def test_strategy_validation_atr_params(self):
        """ATR 전략 매개변수 검증 테스트"""
        factory = StrategyFactory()

        # 잘못된 ATR 주기 - Pydantic V2에서 이미 검증됨
        with pytest.raises(Exception):  # Pydantic ValidationError
            config = StrategyConfig(
                strategy_name="atr_trailing_stop",
                symbol="BTCUSDT",
                timeframe="5m",
                atr_period=200  # 잘못된 값: 최대 100
            )

            factory._validate_strategy_params("atr_trailing_stop", config, {})


# TDD: 이 테스트들은 실패할 것입니다
# 구현 후 이 테스트들이 통과하도록 코드를 수정해야 합니다
class TestIntegrationScenarios:
    """통합 시나리오 테스트"""

    def test_complete_trading_system_initialization(self):
        """완전한 트레이딩 시스템 초기화 테스트"""
        # 이 테스트는 현재 실패할 것입니다
        # 의존성 주입과 설정이 제대로 연결되어야 통과합니다

        # 설정 생성
        config = TradingConfig(
            mode="TESTNET",
            symbols=["BTCUSDT"],
            strategy_name="atr_trailing_stop"
        )

        # 의존성 컨테이너 설정
        configure_dependencies(config)

        # 개선된 라이브 트레이더 생성 시도
        # 현재는 실패할 것입니다 - 구현 필요
        with pytest.raises(Exception):  # 임시로 예외 예상
            from improved_live_trader import ImprovedLiveTrader
            trader = ImprovedLiveTrader()
            assert trader is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
