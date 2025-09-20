"""
개선된 전략 팩토리

의존성 주입 패턴과 설정 관리를 개선하여
전략 생성과 관리를 더 유연하고 테스트하기 쉽게 만듭니다.
"""

from typing import Dict, Any, Optional, Type, Callable
from datetime import datetime

from strategies.base_strategy import Strategy
from strategies.atr_trailing_stop_strategy import ATRTrailingStopStrategy
from strategies.composite_signal_strategy import CompositeSignalStrategy
from core.exceptions import ConfigurationError, ValidationError
from core.data_models import StrategyConfig
from core.dependency_injection import get_config


class StrategyFactory:
    """
    개선된 전략 팩토리

    주요 개선사항:
    - 의존성 주입을 통한 설정 관리
    - 전략별 검증 로직
    - 타입 안전성 보장
    - 확장 가능한 구조
    """

    def __init__(self, config: Optional[StrategyConfig] = None):
        """
        Args:
            config: 전략 설정 (None이면 전역 설정 사용)
        """
        self.config = config
        self._strategy_classes: Dict[str, Type[Strategy]] = {
            "atr_trailing_stop": ATRTrailingStopStrategy,
            "composite_signal": CompositeSignalStrategy,
        }

    def create_strategy(
        self,
        strategy_name: str,
        symbol: str,
        **kwargs
    ) -> Strategy:
        """
        설정과 검증을 통해 전략 인스턴스 생성

        Args:
            strategy_name: 전략 이름
            symbol: 거래 심볼
            **kwargs: 전략별 추가 매개변수

        Returns:
            생성된 전략 인스턴스

        Raises:
            ConfigurationError: 알 수 없는 전략이거나 설정 오류 시
            ValidationError: 전략 매개변수 검증 실패 시
        """
        # 전략 클래스 조회
        strategy_class = self._get_strategy_class(strategy_name)

        # 설정 조회 또는 생성
        config = self._get_or_create_config(strategy_name, symbol, kwargs)

        # 전략별 검증
        self._validate_strategy_params(strategy_name, config, kwargs)

        # 전략 인스턴스 생성
        try:
            return strategy_class(config=config, **kwargs)
        except Exception as e:
            raise ConfigurationError(
                f"Failed to create strategy {strategy_name}: {e}",
                context={"strategy": strategy_name, "symbol": symbol, "error": str(e)}
            ) from e

    def _get_strategy_class(self, strategy_name: str) -> Type[Strategy]:
        """전략 클래스 조회"""
        if strategy_name not in self._strategy_classes:
            raise ConfigurationError(
                f"Unknown strategy: {strategy_name}",
                context={"available_strategies": list(self._strategy_classes.keys())}
            )
        return self._strategy_classes[strategy_name]

    def _get_or_create_config(
        self,
        strategy_name: str,
        symbol: str,
        kwargs: Dict[str, Any]
    ) -> StrategyConfig:
        """전략 설정 조회 또는 생성"""
        if self.config:
            return self.config

        # 전역 설정에서 심볼별 설정 조회
        global_config = get_config()
        symbol_config = global_config.get_strategy_config(symbol)

        # kwargs로 설정 오버라이드
        if kwargs:
            symbol_config = self._override_config(symbol_config, kwargs)

        return symbol_config

    def _override_config(self, base_config: StrategyConfig, overrides: Dict[str, Any]) -> StrategyConfig:
        """설정 오버라이드"""
        config_dict = base_config.dict()
        config_dict.update(overrides)
        return StrategyConfig(**config_dict)

    def _validate_strategy_params(
        self,
        strategy_name: str,
        config: StrategyConfig,
        kwargs: Dict[str, Any]
    ) -> None:
        """전략별 매개변수 검증"""
        if strategy_name == "atr_trailing_stop":
            self._validate_atr_params(config, kwargs)
        elif strategy_name == "composite_signal":
            self._validate_composite_params(config, kwargs)
        else:
            # 기본 검증
            if not hasattr(config, 'symbol') or not config.symbol:
                raise ValidationError("Strategy config must have symbol")

    def _validate_atr_params(self, config: StrategyConfig, kwargs: Dict[str, Any]) -> None:
        """ATR Trailing Stop 전략 매개변수 검증"""
        errors = []

        if config.atr_period and (config.atr_period < 1 or config.atr_period > 100):
            errors.append("ATR period must be between 1 and 100")

        if config.atr_multiplier and (config.atr_multiplier <= 0 or config.atr_multiplier > 10):
            errors.append("ATR multiplier must be between 0 and 10")

        if config.risk_per_trade and (config.risk_per_trade <= 0 or config.risk_per_trade > 1):
            errors.append("Risk per trade must be between 0 and 1")

        if errors:
            raise ValidationError(
                f"ATR strategy parameter validation failed: {', '.join(errors)}",
                context={"config": config.dict(), "kwargs": kwargs}
            )

    def _validate_composite_params(self, config: StrategyConfig, kwargs: Dict[str, Any]) -> None:
        """Composite Signal 전략 매개변수 검증"""
        errors = []

        # 필수 인디케이터 매개변수 검증
        required_params = ['ema_fast', 'ema_slow', 'rsi_length', 'bb_length']
        for param in required_params:
            if getattr(config, param, None) is None:
                errors.append(f"Missing required parameter: {param}")

        # 가중치 합계 검증
        if hasattr(config, 'weights') and config.weights:
            total_weight = sum(config.weights.__dict__.values())
            if abs(total_weight - 1.0) > 0.01:  # 1% 오차 허용
                errors.append(f"Strategy weights must sum to 1.0, got {total_weight}")

        if errors:
            raise ValidationError(
                f"Composite strategy parameter validation failed: {', '.join(errors)}",
                context={"config": config.dict(), "kwargs": kwargs}
            )

    def register_strategy(self, name: str, strategy_class: Type[Strategy]):
        """
        새로운 전략 클래스 등록

        Args:
            name: 전략 이름
            strategy_class: 전략 클래스
        """
        if not issubclass(strategy_class, Strategy):
            raise ConfigurationError(
                f"Strategy class {strategy_class.__name__} must inherit from Strategy"
            )

        self._strategy_classes[name] = strategy_class

    def get_available_strategies(self) -> Dict[str, Type[Strategy]]:
        """사용 가능한 전략 목록 반환"""
        return self._strategy_classes.copy()

    def create_strategy_from_config(
        self,
        symbol: str,
        custom_config: Optional[Dict[str, Any]] = None
    ) -> Strategy:
        """
        설정으로부터 전략 생성

        Args:
            symbol: 심볼
            custom_config: 커스텀 설정 (선택)

        Returns:
            생성된 전략 인스턴스
        """
        # 설정 기반 전략 생성
        if custom_config:
            config = StrategyConfig(**custom_config)
        else:
            config = self._get_or_create_config("atr_trailing_stop", symbol, {})

        return self.create_strategy(
            strategy_name=config.strategy_name,
            symbol=symbol,
            config=config
        )


# 기본 팩토리 인스턴스
_default_factory = None

def get_default_strategy_factory() -> StrategyFactory:
    """기본 전략 팩토리 반환"""
    global _default_factory
    if _default_factory is None:
        _default_factory = StrategyFactory()
    return _default_factory

def create_strategy(
    strategy_name: str,
    symbol: str,
    **kwargs
) -> Strategy:
    """
    편의 함수: 기본 팩토리를 사용해 전략 생성

    Args:
        strategy_name: 전략 이름
        symbol: 심볼
        **kwargs: 전략 매개변수

    Returns:
        생성된 전략 인스턴스
    """
    factory = get_default_strategy_factory()
    return factory.create_strategy(strategy_name, symbol, **kwargs)
