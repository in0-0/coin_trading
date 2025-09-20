"""
Configuration 모듈 - 환경변수와 설정 값들을 중앙화

TDD: Configuration 클래스 구현
"""
import os
import time
from typing import List
from pydantic import BaseModel, Field, field_validator, ConfigDict
from dotenv import load_dotenv


# 환경변수 로드
load_dotenv()


class TradingConfig(BaseModel):
    """거래 관련 설정들"""

    # 기본 심볼 설정
    symbols: List[str] = Field(default_factory=lambda: ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT"])
    execution_interval: int = Field(default=60, ge=1, le=3600)

    # 리스크 관리 설정
    risk_per_trade: float = Field(default=0.005, gt=0.0, le=0.1)
    max_concurrent_positions: int = Field(default=3, ge=1, le=10)
    max_symbol_weight: float = Field(default=0.20, gt=0.0, le=1.0)
    min_order_usdt: float = Field(default=10.0, gt=0.0)

    # ATR 설정
    atr_period: int = Field(default=14, ge=1, le=100)
    atr_multiplier: float = Field(default=0.5, gt=0.0, le=5.0)

    # Bracket 주문 설정
    bracket_k_sl: float = Field(default=1.5, gt=0.0)
    bracket_rr: float = Field(default=2.0, gt=0.0)

    # 실행 설정
    execution_timeframe: str = Field(default="5m")
    strategy_name: str = Field(default="atr_trailing_stop")

    # 주문 실행 설정
    order_execution: str = Field(default="SIMULATED")
    max_slippage_bps: int = Field(default=50, ge=0, le=1000)
    order_timeout_sec: int = Field(default=10, ge=1)
    order_retry: int = Field(default=3, ge=0)
    order_kill_switch: bool = Field(default=False)

    # 로그 설정
    log_file: str = Field(default="live_trader.log")
    live_log_dir: str = Field(default="live_logs")
    run_id: str = Field(default="")

    # 텔레그램 설정
    telegram_bot_token: str = Field(default="")
    telegram_chat_id: str = Field(default="")

    # API 키 설정
    mode: str = Field(default="TESTNET")
    testnet_api_key: str = Field(default="")
    testnet_secret_key: str = Field(default="")
    api_key: str = Field(default="")
    secret_key: str = Field(default="")

    @field_validator('symbols', mode='before')
    @classmethod
    def parse_symbols(cls, v):
        """쉼표로 구분된 문자열을 리스트로 변환"""
        if isinstance(v, str):
            return [s.strip() for s in v.split(',') if s.strip()]
        return v

    @field_validator('run_id', mode='before')
    @classmethod
    def generate_run_id(cls, v):
        """run_id가 비어있으면 자동으로 생성"""
        if not v:
            return time.strftime("%Y%m%d_%H%M%S")
        return v

    @field_validator('order_execution')
    @classmethod
    def validate_order_execution(cls, v):
        """주문 실행 모드 검증"""
        valid_modes = ['SIMULATED', 'LIVE']
        if v.upper() not in valid_modes:
            raise ValueError(f"order_execution must be one of {valid_modes}")
        return v.upper()

    @field_validator('mode')
    @classmethod
    def validate_mode(cls, v):
        """모드 검증"""
        valid_modes = ['TESTNET', 'REAL']
        if v.upper() not in valid_modes:
            raise ValueError(f"mode must be one of {valid_modes}")
        return v.upper()

    model_config = ConfigDict(
        env_file=".env",
        case_sensitive=False
    )


class Configuration:
    """설정 관리 클래스 - 모든 설정을 중앙화"""

    # 상수 정의 (매직 넘버 제거)
    DEFAULT_ATR_PERIOD = 14
    DEFAULT_ATR_MULTIPLIER = 0.5
    DEFAULT_RISK_PER_TRADE = 0.005
    DEFAULT_BRACKET_K_SL = 1.5
    DEFAULT_BRACKET_RR = 2.0
    DEFAULT_MAX_SLIPPAGE_BPS = 50
    DEFAULT_ORDER_TIMEOUT_SEC = 10
    DEFAULT_ORDER_RETRY = 3
    DEFAULT_EXECUTION_INTERVAL = 60
    DEFAULT_MIN_ORDER_USDT = 10.0
    DEFAULT_MAX_SYMBOL_WEIGHT = 0.20
    DEFAULT_MAX_CONCURRENT_POSITIONS = 3

    def __init__(self):
        """환경변수에서 설정 로드"""
        # 환경변수에서 값을 가져와서 검증
        config_data = {
            'symbols': os.getenv("SYMBOLS", "BTCUSDT,ETHUSDT,BNBUSDT,SOLUSDT,XRPUSDT"),
            'execution_interval': int(os.getenv("EXEC_INTERVAL_SECONDS", str(self.DEFAULT_EXECUTION_INTERVAL))),
            'risk_per_trade': float(os.getenv("RISK_PER_TRADE", str(self.DEFAULT_RISK_PER_TRADE))),
            'max_concurrent_positions': int(os.getenv("MAX_CONCURRENT_POS", str(self.DEFAULT_MAX_CONCURRENT_POSITIONS))),
            'max_symbol_weight': float(os.getenv("MAX_SYMBOL_WEIGHT", str(self.DEFAULT_MAX_SYMBOL_WEIGHT))),
            'min_order_usdt': float(os.getenv("MIN_ORDER_USDT", str(self.DEFAULT_MIN_ORDER_USDT))),
            'atr_period': int(os.getenv("ATR_PERIOD", str(self.DEFAULT_ATR_PERIOD))),
            'atr_multiplier': float(os.getenv("ATR_MULTIPLIER", str(self.DEFAULT_ATR_MULTIPLIER))),
            'bracket_k_sl': float(os.getenv("BRACKET_K_SL", str(self.DEFAULT_BRACKET_K_SL))),
            'bracket_rr': float(os.getenv("BRACKET_RR", str(self.DEFAULT_BRACKET_RR))),
            'execution_timeframe': os.getenv("EXECUTION_TIMEFRAME", "5m"),
            'strategy_name': os.getenv("STRATEGY_NAME", "atr_trailing_stop"),
            'order_execution': os.getenv("ORDER_EXECUTION", "SIMULATED"),
            'max_slippage_bps': int(os.getenv("MAX_SLIPPAGE_BPS", str(self.DEFAULT_MAX_SLIPPAGE_BPS))),
            'order_timeout_sec': int(os.getenv("ORDER_TIMEOUT_SEC", str(self.DEFAULT_ORDER_TIMEOUT_SEC))),
            'order_retry': int(os.getenv("ORDER_RETRY", str(self.DEFAULT_ORDER_RETRY))),
            'order_kill_switch': os.getenv("ORDER_KILL_SWITCH", "false").lower() == "true",
            'log_file': os.getenv("LOG_FILE", "live_trader.log"),
            'live_log_dir': os.getenv("LIVE_LOG_DIR", "live_logs"),
            'run_id': os.getenv("RUN_ID", ""),
            'telegram_bot_token': os.getenv("TELEGRAM_BOT_TOKEN", ""),
            'telegram_chat_id': os.getenv("TELEGRAM_CHAT_ID", ""),
            'mode': os.getenv("MODE", "TESTNET"),
            'testnet_api_key': os.getenv("TESTNET_BINANCE_API_KEY", ""),
            'testnet_secret_key': os.getenv("TESTNET_BINANCE_SECRET_KEY", ""),
            'api_key': os.getenv("BINANCE_API_KEY", ""),
            'secret_key': os.getenv("BINANCE_SECRET_KEY", ""),
        }

        # Pydantic 모델로 검증
        self._config = TradingConfig(**config_data)

    def __getattr__(self, name):
        """속성 접근을 Pydantic 모델로 위임"""
        return getattr(self._config, name)

    @property
    def api_key(self) -> str:
        """현재 모드에 따른 API 키 반환"""
        if self._config.mode == "TESTNET":
            return self._config.testnet_api_key
        return self._config.api_key

    @property
    def secret_key(self) -> str:
        """현재 모드에 따른 Secret 키 반환"""
        if self._config.mode == "TESTNET":
            return self._config.testnet_secret_key
        return self._config.secret_key

    def validate(self) -> bool:
        """설정의 유효성을 검증"""
        try:
            # API 키 검증
            if not self.api_key or not self.secret_key:
                print("WARNING: API keys not set. Real orders cannot be placed.")

            # 주문 실행 모드 검증
            if self._config.order_execution == "LIVE":
                if not self.api_key or not self.secret_key:
                    print("ERROR: LIVE mode requires API keys to be set.")
                    return False

            return True
        except Exception as e:
            print(f"Configuration validation error: {e}")
            return False
