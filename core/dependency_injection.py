"""
의존성 주입 및 설정 관리를 위한 컨테이너

이 모듈은 애플리케이션의 의존성을 관리하고 설정을 중앙화합니다.
"""

import os
from typing import Dict, Any, Optional, TypeVar, Type, Callable, Union
from datetime import datetime
from dataclasses import dataclass, field
from dotenv import load_dotenv

from .exceptions import ConfigurationError
from .data_models import StrategyConfig

T = TypeVar('T')

@dataclass
class TradingConfig:
    """전체 트레이딩 시스템 설정"""
    # API 설정
    mode: str = "TESTNET"
    api_key: str = ""
    api_secret: str = ""

    # 심볼 및 시간 설정
    symbols: list[str] = field(default_factory=lambda: ["BTCUSDT"])
    execution_interval: int = 60
    execution_timeframe: str = "5m"

    # 전략 설정
    strategy_name: str = "atr_trailing_stop"
    strategy_configs: Dict[str, StrategyConfig] = field(default_factory=dict)

    # 리스크 관리
    risk_per_trade: float = 0.005
    max_concurrent_positions: int = 3
    max_symbol_weight: float = 0.20
    min_order_usdt: float = 10.0

    # 트레일링 스탑 설정
    atr_period: int = 14
    atr_multiplier: float = 0.5
    bracket_k_sl: float = 1.5
    bracket_rr: float = 2.0

    # 주문 실행 설정
    order_execution: str = "SIMULATED"
    max_slippage_bps: int = 50
    order_timeout_sec: int = 10
    order_retry: int = 3
    kill_switch: bool = False

    # 로깅 설정
    log_file: str = "live_trader.log"
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # 라이브 로그 설정
    live_log_dir: str = "live_logs"
    run_id: str = ""
    live_log_date_partition: bool = True
    log_tz: str = "UTC"
    log_date_fmt: str = "%Y%m%d"

    @classmethod
    def from_env(cls) -> 'TradingConfig':
        """환경변수로부터 설정 로드"""
        config = cls()
        load_dotenv()

        # API 설정
        config.mode = os.getenv("MODE", "TESTNET").upper()
        if config.mode not in ("TESTNET", "REAL"):
            raise ConfigurationError(
                "MODE must be TESTNET or REAL",
                config_key="MODE",
                valid_values=["TESTNET", "REAL"]
            )

        if config.mode == "TESTNET":
            config.api_key = os.getenv("TESTNET_BINANCE_API_KEY", "")
            config.api_secret = os.getenv("TESTNET_BINANCE_SECRET_KEY", "")
        else:
            config.api_key = os.getenv("BINANCE_API_KEY", "")
            config.api_secret = os.getenv("BINANCE_SECRET_KEY", "")
        

        # 심볼 및 시간 설정
        symbols_str = os.getenv("SYMBOLS", "BTCUSDT,ETHUSDT,BNBUSDT,SOLUSDT,XRPUSDT")
        config.symbols = [s.strip() for s in symbols_str.split(",") if s.strip()]
        config.execution_interval = int(os.getenv("EXEC_INTERVAL_SECONDS", "60"))
        config.execution_timeframe = os.getenv("EXECUTION_TIMEFRAME", "5m")

        # 전략 설정
        config.strategy_name = os.getenv("STRATEGY_NAME", "atr_trailing_stop")

        # 리스크 관리
        config.risk_per_trade = float(os.getenv("RISK_PER_TRADE", "0.005"))
        config.max_concurrent_positions = int(os.getenv("MAX_CONCURRENT_POS", "3"))
        config.max_symbol_weight = float(os.getenv("MAX_SYMBOL_WEIGHT", "0.20"))
        config.min_order_usdt = float(os.getenv("MIN_ORDER_USDT", "10.0"))

        # 트레일링 스탑 설정
        config.atr_period = int(os.getenv("ATR_PERIOD", "14"))
        config.atr_multiplier = float(os.getenv("ATR_MULTIPLIER", "0.5"))
        config.bracket_k_sl = float(os.getenv("BRACKET_K_SL", "1.5"))
        config.bracket_rr = float(os.getenv("BRACKET_RR", "2.0"))

        # 주문 실행 설정
        config.order_execution = os.getenv("ORDER_EXECUTION", "SIMULATED").upper()
        config.max_slippage_bps = int(os.getenv("MAX_SLIPPAGE_BPS", "50"))
        config.order_timeout_sec = int(os.getenv("ORDER_TIMEOUT_SEC", "10"))
        config.order_retry = int(os.getenv("ORDER_RETRY", "3"))
        config.kill_switch = os.getenv("ORDER_KILL_SWITCH", "false").lower() == "true"

        # 로깅 설정
        config.log_file = os.getenv("LOG_FILE", "live_trader.log")
        config.telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        config.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", "")

        # 라이브 로그 설정
        config.live_log_dir = os.getenv("LIVE_LOG_DIR", "live_logs")
        config.run_id = os.getenv("RUN_ID", "")
        config.live_log_date_partition = os.getenv("LIVE_LOG_DATE_PARTITION", "1").lower() in ("1", "true", "yes", "on")
        config.log_tz = os.getenv("LOG_TZ", "UTC")
        config.log_date_fmt = os.getenv("LOG_DATE_FMT", "%Y%m%d")

        return config

    def validate(self) -> list[str]:
        """설정 유효성 검증"""
        errors = []

        if not self.api_key or not self.api_secret:
            errors.append("API keys are required")

        if not self.symbols:
            errors.append("At least one symbol must be specified")

        if self.risk_per_trade <= 0 or self.risk_per_trade > 1:
            errors.append("Risk per trade must be between 0 and 1")

        if self.max_symbol_weight <= 0 or self.max_symbol_weight > 1:
            errors.append("Max symbol weight must be between 0 and 1")

        if self.min_order_usdt <= 0:
            errors.append("Min order USDT must be positive")

        if self.execution_interval <= 0:
            errors.append("Execution interval must be positive")

        return errors

    def get_strategy_config(self, symbol: str) -> StrategyConfig:
        """심볼별 전략 설정 반환 (Composite 전략 상세 설정 지원)"""
        if symbol in self.strategy_configs:
            return self.strategy_configs[symbol]

        # 기본 전략 설정 생성
        config = StrategyConfig(
            strategy_name=self.strategy_name,
            symbol=symbol,
            timeframe=self.execution_timeframe,
            atr_period=self.atr_period,
            atr_multiplier=self.atr_multiplier,
            risk_per_trade=self.risk_per_trade,
            max_position_size=self.max_symbol_weight
        )

        # Composite 전략의 경우 상세 설정 추가
        if self.strategy_name == "composite_signal":
            config = self._enhance_composite_config(config)

        self.strategy_configs[symbol] = config
        return config

    def _enhance_composite_config(self, base_config: StrategyConfig) -> StrategyConfig:
        """Composite 전략 설정 강화"""
        # Composite 전략의 기본 설정값들을 추가
        enhanced_config = StrategyConfig(
            strategy_name=base_config.strategy_name,
            symbol=base_config.symbol,
            timeframe=base_config.timeframe,
            atr_period=base_config.atr_period,
            atr_multiplier=base_config.atr_multiplier,
            risk_per_trade=base_config.risk_per_trade,
            max_position_size=base_config.max_position_size,
            # Composite 전략 특화 설정
            ema_fast=12,
            ema_slow=26,
            bb_len=20,
            rsi_len=14,
            macd_fast=12,
            macd_slow=26,
            macd_signal=9,
            atr_len=14,
            k_atr_norm=1.0,
            vol_len=20,
            obv_span=20,
            max_score=1.0,
            buy_threshold=0.3,
            sell_threshold=-0.3,
            weights=type('Weights', (), {
                'ma': 0.25, 'bb': 0.15, 'rsi': 0.15, 'macd': 0.25, 'vol': 0.1, 'obv': 0.1
            })(),
            # RSI와 BB의 매개변수명도 추가
            rsi_length=14,
            bb_length=20
        )
        return enhanced_config


class DependencyContainer:
    """
    의존성 주입 컨테이너

    애플리케이션의 모든 의존성을 관리하고 제공합니다.
    """

    def __init__(self):
        self._config: Optional[TradingConfig] = None
        self._instances: Dict[str, Any] = {}
        self._factories: Dict[str, Callable] = {}

    def register_config(self, config: TradingConfig):
        """설정 등록"""
        self._config = config

    def get_config(self) -> TradingConfig:
        """설정 반환"""
        if not self._config:
            self._config = TradingConfig.from_env()
        return self._config

    def register_instance(self, key: str, instance: Any):
        """인스턴스 등록"""
        self._instances[key] = instance

    def get_instance(self, key: str) -> Any:
        """등록된 인스턴스 반환"""
        return self._instances.get(key)

    def register_factory(self, key: str, factory: Callable[..., Any]):
        """팩토리 등록"""
        self._factories[key] = factory

    def create_instance(self, key: str, **kwargs) -> Any:
        """팩토리를 사용해 인스턴스 생성"""
        if key not in self._factories:
            raise ConfigurationError(f"No factory registered for {key}")

        factory = self._factories[key]
        return factory(**kwargs)

    def lazy_get(self, key: str, factory: Callable[..., Any], **kwargs) -> Any:
        """
        지연 초기화로 인스턴스 반환

        이미 존재하면 반환, 없으면 팩토리로 생성
        """
        if key in self._instances:
            return self._instances[key]

        instance = factory(**kwargs)
        self._instances[key] = instance
        return instance


# 전역 의존성 컨테이너
_container = DependencyContainer()

def get_container() -> DependencyContainer:
    """전역 의존성 컨테이너 반환"""
    return _container

def configure_dependencies(config: Optional[TradingConfig] = None):
    """의존성 컨테이너 설정"""
    if config:
        _container.register_config(config)

def get_config() -> TradingConfig:
    """설정 반환"""
    return _container.get_config()

def register_service(key: str, factory: Callable[..., Any]):
    """서비스 팩토리 등록"""
    _container.register_factory(key, factory)

def get_service(key: str, **kwargs) -> Any:
    """서비스 인스턴스 반환"""
    return _container.create_instance(key, **kwargs)

def lazy_service(key: str, factory: Callable[..., Any], **kwargs) -> Any:
    """지연 초기화 서비스 반환"""
    return _container.lazy_get(key, factory, **kwargs)
