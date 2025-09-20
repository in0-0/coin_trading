"""
Constants 모듈 - 매직 넘버와 하드코딩된 값들을 중앙화

TDD: TradingConstants 클래스 구현
"""


class TradingConstants:
    """
    거래 시스템에서 사용되는 모든 상수들을 중앙화

    이 클래스는 프로젝트 내 모든 매직 넘버와 하드코딩된 값들을
    한 곳에서 관리하여 코드의 유지보수성과 일관성을 높입니다.
    """

    # === ATR 관련 상수들 ===
    DEFAULT_ATR_PERIOD: int = 14
    DEFAULT_ATR_MULTIPLIER: float = 0.5
    MIN_ATR_PERIOD: int = 1
    MAX_ATR_PERIOD: int = 100
    MIN_ATR_MULTIPLIER: float = 0.0
    MAX_ATR_MULTIPLIER: float = 5.0

    # === 리스크 관리 상수들 ===
    DEFAULT_RISK_PER_TRADE: float = 0.005  # 0.5%
    MIN_RISK_PER_TRADE: float = 0.0001  # 0.01%
    MAX_RISK_PER_TRADE: float = 0.1     # 10%

    # === 주문 설정 상수들 ===
    DEFAULT_MAX_SLIPPAGE_BPS: int = 50      # 0.5%
    DEFAULT_ORDER_TIMEOUT_SEC: int = 10     # 10초
    DEFAULT_ORDER_RETRY: int = 3
    MIN_ORDER_TIMEOUT_SEC: int = 1
    MAX_ORDER_TIMEOUT_SEC: int = 300        # 5분
    MIN_ORDER_RETRY: int = 0
    MAX_ORDER_RETRY: int = 10
    MIN_SLIPPAGE_BPS: int = 0
    MAX_SLIPPAGE_BPS: int = 1000            # 10%

    # === Bracket 주문 상수들 ===
    DEFAULT_BRACKET_K_SL: float = 1.5       # 손절배율
    DEFAULT_BRACKET_RR: float = 2.0         # 익절배율
    MIN_BRACKET_K_SL: float = 0.1
    MAX_BRACKET_K_SL: float = 10.0
    MIN_BRACKET_RR: float = 0.1
    MAX_BRACKET_RR: float = 10.0

    # === 포지션 제한 상수들 ===
    DEFAULT_MAX_CONCURRENT_POSITIONS: int = 3
    DEFAULT_MAX_SYMBOL_WEIGHT: float = 0.20     # 20%
    DEFAULT_MIN_ORDER_USDT: float = 10.0
    MIN_MAX_CONCURRENT_POSITIONS: int = 1
    MAX_MAX_CONCURRENT_POSITIONS: int = 20
    MIN_MAX_SYMBOL_WEIGHT: float = 0.01         # 1%
    MAX_MAX_SYMBOL_WEIGHT: float = 1.0          # 100%
    MIN_MIN_ORDER_USDT: float = 1.0

    # === 실행 설정 상수들 ===
    DEFAULT_EXECUTION_INTERVAL: int = 60        # 60초
    MIN_EXECUTION_INTERVAL: int = 1             # 1초
    MAX_EXECUTION_INTERVAL: int = 3600          # 1시간

    # === 거래 모드 상수들 ===
    VALID_ORDER_EXECUTIONS = ['SIMULATED', 'LIVE']
    VALID_TRADING_MODES = ['TESTNET', 'REAL']

    # === API 관련 상수들 ===
    API_REQUEST_TIMEOUT: int = 30               # 30초
    API_MAX_RETRIES: int = 5

    # === 시간 관련 상수들 ===
    SECONDS_PER_MINUTE: int = 60
    SECONDS_PER_HOUR: int = 3600
    SECONDS_PER_DAY: int = 86400

    # === 수학 상수들 ===
    BPS_TO_DECIMAL: float = 0.0001              # 1bps = 0.0001
    PERCENT_TO_DECIMAL: float = 0.01            # 1% = 0.01

    # === 기본 심볼 목록 ===
    DEFAULT_SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT"]

    # === 로그 관련 상수들 ===
    DEFAULT_LOG_LEVEL = "INFO"
    DEFAULT_LOG_FILE = "live_trader.log"
    DEFAULT_LIVE_LOG_DIR = "live_logs"

    # === 타임프레임 관련 상수들 ===
    VALID_TIMEFRAMES = ["1m", "5m", "15m", "1h", "4h", "1d"]
    DEFAULT_EXECUTION_TIMEFRAME = "5m"

    # === 전략 관련 상수들 ===
    DEFAULT_STRATEGY_NAME = "atr_trailing_stop"
    VALID_STRATEGY_NAMES = ["atr_trailing_stop", "composite_signal"]

    # === 통계 관련 상수들 ===
    DEFAULT_WIN_RATE: float = 0.5               # 50%
    DEFAULT_AVG_WIN: float = 1.0                # 1배
    DEFAULT_AVG_LOSS: float = 1.0               # 1배
    DEFAULT_KELLY_FMAX: float = 0.2             # 20%

    @classmethod
    def get_atr_range(cls) -> tuple[int, int]:
        """ATR 기간의 유효 범위를 반환"""
        return (cls.MIN_ATR_PERIOD, cls.MAX_ATR_PERIOD)

    @classmethod
    def get_atr_multiplier_range(cls) -> tuple[float, float]:
        """ATR 승수의 유효 범위를 반환"""
        return (cls.MIN_ATR_MULTIPLIER, cls.MAX_ATR_MULTIPLIER)

    @classmethod
    def get_risk_per_trade_range(cls) -> tuple[float, float]:
        """리스크 비율의 유효 범위를 반환"""
        return (cls.MIN_RISK_PER_TRADE, cls.MAX_RISK_PER_TRADE)

    @classmethod
    def get_max_slippage_range(cls) -> tuple[int, int]:
        """최대 슬리피지의 유효 범위를 반환 (bps)"""
        return (cls.MIN_SLIPPAGE_BPS, cls.MAX_SLIPPAGE_BPS)

    @classmethod
    def is_valid_order_execution(cls, mode: str) -> bool:
        """주문 실행 모드가 유효한지 확인"""
        return mode.upper() in cls.VALID_ORDER_EXECUTIONS

    @classmethod
    def is_valid_trading_mode(cls, mode: str) -> bool:
        """거래 모드가 유효한지 확인"""
        return mode.upper() in cls.VALID_TRADING_MODES

    @classmethod
    def is_valid_strategy_name(cls, name: str) -> bool:
        """전략 이름이 유효한지 확인"""
        return name in cls.VALID_STRATEGY_NAMES

    @classmethod
    def is_valid_timeframe(cls, timeframe: str) -> bool:
        """타임프레임이 유효한지 확인"""
        return timeframe in cls.VALID_TIMEFRAMES
