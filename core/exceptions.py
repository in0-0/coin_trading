"""
커스텀 예외 클래스들 - 일관성 있는 에러 처리

TDD: 커스텀 예외 클래스 구현
"""
from datetime import datetime
from typing import Dict, Any, Optional


class TradingError(Exception):
    """
    거래 시스템의 기본 예외 클래스

    모든 거래 관련 예외의 베이스 클래스가 되며,
    타임스탬프와 컨텍스트 정보를 제공합니다.
    """

    def __init__(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None
    ):
        """
        Args:
            message: 오류 메시지
            context: 오류 발생 시 추가 컨텍스트 정보
            timestamp: 오류 발생 시간 (미제공 시 현재 시간 사용)
        """
        super().__init__(message)
        self.message = message
        self.context = context or {}
        self.timestamp = timestamp or datetime.now()

    def __str__(self) -> str:
        """사용자 친화적인 오류 메시지 반환"""
        context_str = ""
        if self.context:
            context_items = [f"{k}={v}" for k, v in self.context.items()]
            context_str = f" (Context: {', '.join(context_items)})"

        return f"{self.message}{context_str} [{self.timestamp.isoformat()}]"


class OrderError(TradingError):
    """
    주문 관련 오류

    주문 생성, 실행, 취소 등과 관련된 모든 오류를 처리합니다.
    """

    def __init__(
        self,
        message: str,
        symbol: Optional[str] = None,
        order_id: Optional[str] = None,
        side: Optional[str] = None,
        quantity: Optional[float] = None,
        price: Optional[float] = None,
        context: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None
    ):
        """
        Args:
            message: 오류 메시지
            symbol: 관련 심볼 (예: 'BTCUSDT')
            order_id: 주문 ID
            side: 주문 방향 ('BUY' 또는 'SELL')
            quantity: 주문 수량
            price: 주문 가격
            context: 추가 컨텍스트 정보
            timestamp: 오류 발생 시간
        """
        super().__init__(message, context, timestamp)

        # 주문 관련 속성들
        self.symbol = symbol
        self.order_id = order_id
        self.side = side
        self.quantity = quantity
        self.price = price

    def __str__(self) -> str:
        """주문 관련 정보를 포함한 오류 메시지 반환"""
        order_info = []
        if self.symbol:
            order_info.append(f"Symbol: {self.symbol}")
        if self.order_id:
            order_info.append(f"OrderID: {self.order_id}")
        if self.side:
            order_info.append(f"Side: {self.side}")
        if self.quantity is not None:
            order_info.append(f"Quantity: {self.quantity}")
        if self.price is not None:
            order_info.append(f"Price: {self.price}")

        order_str = f" ({', '.join(order_info)})" if order_info else ""

        return f"{self.message}{order_str}"


class ConfigurationError(TradingError):
    """
    설정 관련 오류

    환경변수, 설정 파일 등과 관련된 모든 오류를 처리합니다.
    """

    def __init__(
        self,
        message: str,
        config_key: Optional[str] = None,
        config_value: Optional[Any] = None,
        expected_type: Optional[type] = None,
        valid_values: Optional[list] = None,
        context: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None
    ):
        """
        Args:
            message: 오류 메시지
            config_key: 문제가 된 설정 키
            config_value: 문제가 된 설정 값
            expected_type: 예상되는 타입
            valid_values: 유효한 값들의 리스트
            context: 추가 컨텍스트 정보
            timestamp: 오류 발생 시간
        """
        super().__init__(message, context, timestamp)

        # 설정 관련 속성들
        self.config_key = config_key
        self.config_value = config_value
        self.expected_type = expected_type
        self.valid_values = valid_values

    def __str__(self) -> str:
        """설정 관련 정보를 포함한 오류 메시지 반환"""
        config_info = []
        if self.config_key:
            config_info.append(f"Key: {self.config_key}")
        if self.config_value is not None:
            config_info.append(f"Value: {self.config_value}")
        if self.expected_type:
            config_info.append(f"Expected Type: {self.expected_type.__name__}")
        if self.valid_values:
            config_info.append(f"Valid Values: {self.valid_values}")

        config_str = f" ({', '.join(config_info)})" if config_info else ""

        return f"{self.message}{config_str}"


class DataError(TradingError):
    """
    데이터 관련 오류

    가격 데이터, 인디케이터 계산 등과 관련된 모든 오류를 처리합니다.
    """

    def __init__(
        self,
        message: str,
        symbol: Optional[str] = None,
        timeframe: Optional[str] = None,
        data_points: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None
    ):
        """
        Args:
            message: 오류 메시지
            symbol: 관련 심볼
            timeframe: 관련 타임프레임
            data_points: 데이터 포인트 수
            context: 추가 컨텍스트 정보
            timestamp: 오류 발생 시간
        """
        super().__init__(message, context, timestamp)

        # 데이터 관련 속성들
        self.symbol = symbol
        self.timeframe = timeframe
        self.data_points = data_points

    def __str__(self) -> str:
        """데이터 관련 정보를 포함한 오류 메시지 반환"""
        data_info = []
        if self.symbol:
            data_info.append(f"Symbol: {self.symbol}")
        if self.timeframe:
            data_info.append(f"Timeframe: {self.timeframe}")
        if self.data_points is not None:
            data_info.append(f"Data Points: {self.data_points}")

        data_str = f" ({', '.join(data_info)})" if data_info else ""

        return f"{self.message}{data_str}"


class StrategyError(TradingError):
    """
    전략 관련 오류

    신호 생성, 인디케이터 계산 등과 관련된 모든 오류를 처리합니다.
    """

    def __init__(
        self,
        message: str,
        strategy_name: Optional[str] = None,
        signal: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None
    ):
        """
        Args:
            message: 오류 메시지
            strategy_name: 전략 이름
            signal: 생성된 신호 (BUY, SELL, HOLD 등)
            context: 추가 컨텍스트 정보
            timestamp: 오류 발생 시간
        """
        super().__init__(message, context, timestamp)

        # 전략 관련 속성들
        self.strategy_name = strategy_name
        self.signal = signal

    def __str__(self) -> str:
        """전략 관련 정보를 포함한 오류 메시지 반환"""
        strategy_info = []
        if self.strategy_name:
            strategy_info.append(f"Strategy: {self.strategy_name}")
        if self.signal:
            strategy_info.append(f"Signal: {self.signal}")

        strategy_str = f" ({', '.join(strategy_info)})" if strategy_info else ""

        return f"{self.message}{strategy_str}"


class NetworkError(TradingError):
    """
    네트워크 관련 오류

    API 호출, 연결 등과 관련된 모든 오류를 처리합니다.
    """

    def __init__(
        self,
        message: str,
        endpoint: Optional[str] = None,
        status_code: Optional[int] = None,
        retry_count: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None
    ):
        """
        Args:
            message: 오류 메시지
            endpoint: API 엔드포인트
            status_code: HTTP 상태 코드
            retry_count: 재시도 횟수
            context: 추가 컨텍스트 정보
            timestamp: 오류 발생 시간
        """
        super().__init__(message, context, timestamp)

        # 네트워크 관련 속성들
        self.endpoint = endpoint
        self.status_code = status_code
        self.retry_count = retry_count

    def __str__(self) -> str:
        """네트워크 관련 정보를 포함한 오류 메시지 반환"""
        network_info = []
        if self.endpoint:
            network_info.append(f"Endpoint: {self.endpoint}")
        if self.status_code is not None:
            network_info.append(f"Status Code: {self.status_code}")
        if self.retry_count is not None:
            network_info.append(f"Retry Count: {self.retry_count}")

        network_str = f" ({', '.join(network_info)})" if network_info else ""

        return f"{self.message}{network_str}"


class ValidationError(TradingError):
    """
    검증 관련 오류

    입력값 검증, 비즈니스 규칙 위반 등과 관련된 모든 오류를 처리합니다.
    """

    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        value: Optional[Any] = None,
        constraint: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None
    ):
        """
        Args:
            message: 오류 메시지
            field: 검증 실패한 필드명
            value: 검증 실패한 값
            constraint: 위반된 제약조건
            context: 추가 컨텍스트 정보
            timestamp: 오류 발생 시간
        """
        super().__init__(message, context, timestamp)

        # 검증 관련 속성들
        self.field = field
        self.value = value
        self.constraint = constraint

    def __str__(self) -> str:
        """검증 관련 정보를 포함한 오류 메시지 반환"""
        validation_info = []
        if self.field:
            validation_info.append(f"Field: {self.field}")
        if self.value is not None:
            validation_info.append(f"Value: {self.value}")
        if self.constraint:
            validation_info.append(f"Constraint: {self.constraint}")

        validation_str = f" ({', '.join(validation_info)})" if validation_info else ""

        return f"{self.message}{validation_str}"
