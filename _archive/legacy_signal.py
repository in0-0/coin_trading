"""
Signal 및 Action 구조 개선 모듈

현재 Signal Enum의 문제점들을 해결하고 더 나은 구조로 개선합니다.
기존 호환성을 유지하면서 확장성과 타입 안정성을 제공합니다.
"""
from enum import Enum
from typing import Union, Optional
from dataclasses import dataclass
from datetime import datetime


class SignalType(Enum):
    """신호의 기본 타입을 정의"""
    HOLD = "hold"
    BUY = "buy"
    SELL = "sell"


class SignalAction(Enum):
    """신호 액션 타입을 정의"""
    ENTRY = "entry"         # 신규 진입
    ADD = "add"             # 포지션 추가 (불타기/물타기)
    EXIT = "exit"           # 포지션 청산
    PARTIAL_EXIT = "partial_exit"  # 부분 청산
    STOP_UPDATE = "stop_update"    # 스탑 업데이트


@dataclass
class TradingSignal:
    """
    개선된 거래 신호 클래스

    기존 Signal Enum의 문제점들을 해결:
    - 상태와 액션을 명확히 분리
    - 확장 가능하고 타입 안정성 제공
    - 풍부한 컨텍스트 정보 포함
    """

    signal_type: SignalType
    action: SignalAction
    confidence: float = 0.0
    metadata: Optional[dict] = None
    timestamp: Optional[datetime] = None

    def __post_init__(self):
        """초기화 후 타임스탬프 설정"""
        if self.timestamp is None:
            self.timestamp = datetime.now()

        if self.metadata is None:
            self.metadata = {}

    @property
    def is_buy(self) -> bool:
        """매수 신호인지 확인"""
        return self.signal_type == SignalType.BUY

    @property
    def is_sell(self) -> bool:
        """매도 신호인지 확인"""
        return self.signal_type == SignalType.SELL

    @property
    def is_hold(self) -> bool:
        """홀드 신호인지 확인"""
        return self.signal_type == SignalType.HOLD

    @property
    def is_entry(self) -> bool:
        """진입 신호인지 확인"""
        return self.action == SignalAction.ENTRY

    @property
    def is_add_position(self) -> bool:
        """포지션 추가 신호인지 확인"""
        return self.action == SignalAction.ADD

    @property
    def is_exit(self) -> bool:
        """청산 신호인지 확인"""
        return self.action == SignalAction.EXIT

    @property
    def is_partial_exit(self) -> bool:
        """부분 청산 신호인지 확인"""
        return self.action == SignalAction.PARTIAL_EXIT

    @property
    def is_stop_update(self) -> bool:
        """스탑 업데이트 신호인지 확인"""
        return self.action == SignalAction.STOP_UPDATE

    def __str__(self) -> str:
        """사용자 친화적인 문자열 표현"""
        action_desc = {
            SignalAction.ENTRY: "진입",
            SignalAction.ADD: "추가",
            SignalAction.EXIT: "청산",
            SignalAction.PARTIAL_EXIT: "부분청산",
            SignalAction.STOP_UPDATE: "스탑업데이트"
        }

        signal_desc = {
            SignalType.HOLD: "홀드",
            SignalType.BUY: "매수",
            SignalType.SELL: "매도"
        }

        confidence_str = f" (신뢰도: {self.confidence:.1%})" if self.confidence > 0 else ""
        metadata_str = f" {self.metadata}" if self.metadata else ""

        return f"{signal_desc[self.signal_type]} {action_desc[self.action]}{confidence_str}{metadata_str}"


# 기존 Signal Enum과의 호환성을 위한 어댑터
class Signal(Enum):
    """
    기존 Signal Enum과의 호환성을 유지

    새로운 TradingSignal 구조로 마이그레이션하는 동안
    기존 코드를 깨지 않도록 유지
    """
    HOLD = 0
    BUY = 1
    SELL = 2
    BUY_NEW = 3      # 신규 진입 (deprecated: 대신 TradingSignal 사용)
    BUY_ADD = 4      # 불타기/물타기 (deprecated: 대신 TradingSignal 사용)
    SELL_PARTIAL = 5 # 부분 청산 (deprecated: 대신 TradingSignal 사용)
    SELL_ALL = 6     # 전량 청산 (deprecated: 대신 TradingSignal 사용)
    UPDATE_TRAIL = 7 # 트레일링 업데이트 (deprecated: 대신 TradingSignal 사용)

    @classmethod
    def from_trading_signal(cls, trading_signal: TradingSignal) -> 'Signal':
        """TradingSignal로부터 기존 Signal로 변환"""
        if trading_signal.is_hold:
            return cls.HOLD
        elif trading_signal.is_buy and trading_signal.is_entry:
            return cls.BUY_NEW
        elif trading_signal.is_buy and trading_signal.is_add_position:
            return cls.BUY_ADD
        elif trading_signal.is_sell and trading_signal.is_partial_exit:
            return cls.SELL_PARTIAL
        elif trading_signal.is_sell and trading_signal.is_exit:
            return cls.SELL_ALL
        elif trading_signal.is_sell and trading_signal.is_stop_update:
            return cls.UPDATE_TRAIL
        elif trading_signal.is_buy:
            return cls.BUY
        elif trading_signal.is_sell:
            return cls.SELL
        else:
            return cls.HOLD

    def to_trading_signal(self, confidence: float = 0.0, metadata: Optional[dict] = None) -> TradingSignal:
        """기존 Signal로부터 TradingSignal로 변환"""
        if self == Signal.HOLD:
            return TradingSignal(SignalType.HOLD, SignalAction.EXIT, confidence, metadata)
        elif self == Signal.BUY_NEW:
            return TradingSignal(SignalType.BUY, SignalAction.ENTRY, confidence, metadata)
        elif self == Signal.BUY_ADD:
            return TradingSignal(SignalType.BUY, SignalAction.ADD, confidence, metadata)
        elif self == Signal.SELL_PARTIAL:
            return TradingSignal(SignalType.SELL, SignalAction.PARTIAL_EXIT, confidence, metadata)
        elif self == Signal.SELL_ALL:
            return TradingSignal(SignalType.SELL, SignalAction.EXIT, confidence, metadata)
        elif self == Signal.UPDATE_TRAIL:
            return TradingSignal(SignalType.SELL, SignalAction.STOP_UPDATE, confidence, metadata)
        elif self == Signal.BUY:
            return TradingSignal(SignalType.BUY, SignalAction.ENTRY, confidence, metadata)
        elif self == Signal.SELL:
            return TradingSignal(SignalType.SELL, SignalAction.EXIT, confidence, metadata)
        else:
            return TradingSignal(SignalType.HOLD, SignalAction.EXIT, confidence, metadata)


# 편의 함수들
def create_buy_signal(action: SignalAction = SignalAction.ENTRY, confidence: float = 0.0, metadata: Optional[dict] = None) -> TradingSignal:
    """매수 신호 생성"""
    return TradingSignal(SignalType.BUY, action, confidence, metadata)


def create_sell_signal(action: SignalAction = SignalAction.EXIT, confidence: float = 0.0, metadata: Optional[dict] = None) -> TradingSignal:
    """매도 신호 생성"""
    return TradingSignal(SignalType.SELL, action, confidence, metadata)


def create_hold_signal(confidence: float = 0.0, metadata: Optional[dict] = None) -> TradingSignal:
    """홀드 신호 생성"""
    return TradingSignal(SignalType.HOLD, SignalAction.EXIT, confidence, metadata)


# 기존 코드와의 호환성을 위한 타입 별칭
SignalLike = Union[Signal, TradingSignal]
