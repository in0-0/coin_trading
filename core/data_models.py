"""
Pydantic 모델을 활용한 데이터 검증 및 타입 안정성

이 모듈은 거래 시스템에서 사용하는 데이터 모델들을 정의합니다.
Pydantic을 사용하여 런타임 타입 검증과 데이터 변환을 제공합니다.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict
from enum import Enum

from .exceptions import ValidationError


class KlineData(BaseModel):
    """바이낸스 Kline 데이터 모델"""

    open_time: datetime = Field(..., description="캔들 시작 시간")
    open_price: Decimal = Field(..., ge=0, description="시가")
    high_price: Decimal = Field(..., ge=0, description="고가")
    low_price: Decimal = Field(..., ge=0, description="저가")
    close_price: Decimal = Field(..., ge=0, description="종가")
    volume: Decimal = Field(..., ge=0, description="거래량")
    close_time: datetime = Field(..., description="캔들 종료 시간")
    quote_asset_volume: Decimal = Field(..., ge=0, description="기준 자산 거래량")
    number_of_trades: int = Field(..., ge=0, description="거래 수")
    taker_buy_base_asset_volume: Decimal = Field(..., ge=0, description="테이커 매수 기준 자산 거래량")
    taker_buy_quote_asset_volume: Decimal = Field(..., ge=0, description="테이커 매수 기준 통화 거래량")
    ignore: Optional[Any] = Field(None, description="무시 필드")

    @field_validator('open_time', 'close_time')
    @classmethod
    def validate_timestamps(cls, v):
        """타임스탬프가 미래 시간인지 검증"""
        if v > datetime.now(timezone.utc):
            raise ValueError('Timestamp cannot be in the future')
        return v

    @model_validator(mode='after')
    def validate_price_consistency(self):
        """가격 일관성 검증 (고가 >= 시가, 고가 >= 종가, 저가 <= 시가, 저가 <= 종가)"""
        if self.open_price > self.high_price:
            raise ValueError('Open price cannot be higher than high price')

        if self.open_price < self.low_price:
            raise ValueError('Open price cannot be lower than low price')

        if self.close_price > self.high_price:
            raise ValueError('Close price cannot be higher than high price')

        if self.close_price < self.low_price:
            raise ValueError('Close price cannot be lower than low price')

        return self

    @model_validator(mode='after')
    def validate_time_order(self):
        """캔들 시간 순서 검증"""
        if self.open_time >= self.close_time:
            raise ValueError('Open time must be before close time')

        return self

    model_config = ConfigDict(
        json_encoders={
            datetime: lambda v: v.isoformat(),
            Decimal: lambda v: str(v)
        }
    )


class NormalizedKlineData(BaseModel):
    """정규화된 Kline 데이터 (타겟 컬럼만 포함)"""

    open_time: datetime = Field(..., description="캔들 시작 시간")
    open: float = Field(..., ge=0, description="시가")
    high: float = Field(..., ge=0, description="고가")
    low: float = Field(..., ge=0, description="저가")
    close: float = Field(..., ge=0, description="종가")
    volume: float = Field(..., ge=0, description="거래량")

    @field_validator('open_time')
    @classmethod
    def validate_timestamp_not_future(cls, v):
        """타임스탬프가 미래가 아닌지 검증"""
        if v > datetime.now(timezone.utc):
            raise ValueError('Timestamp cannot be in the future')
        return v

    @model_validator(mode='after')
    def validate_price_logic(self):
        """가격 논리 검증"""
        if self.open > self.high:
            raise ValueError('Open price cannot be higher than high price')

        if self.open < self.low:
            raise ValueError('Open price cannot be lower than low price')

        if self.close > self.high:
            raise ValueError('Close price cannot be higher than high price')

        if self.close < self.low:
            raise ValueError('Close price cannot be lower than low price')

        return self

    model_config = ConfigDict(
        json_encoders={
            datetime: lambda v: v.isoformat()
        }
    )


class MarketDataSummary(BaseModel):
    """시장 데이터 요약 정보"""

    symbol: str = Field(..., pattern=r'^[A-Z0-9]{2,20}$', description="거래 심볼 (예: BTCUSDT)")
    timeframe: str = Field(..., pattern=r'^[0-9]+[smhd]$', description="타임프레임 (예: 5m, 1h, 1d)")
    data_points: int = Field(..., ge=0, description="데이터 포인트 수")
    start_time: datetime = Field(..., description="데이터 시작 시간")
    end_time: datetime = Field(..., description="데이터 종료 시간")
    latest_price: Optional[float] = Field(None, ge=0, description="최신 가격")
    volume_24h: Optional[float] = Field(None, ge=0, description="24시간 거래량")

    @model_validator(mode='after')
    def validate_time_order(self):
        """시간 순서 검증"""
        if self.start_time >= self.end_time:
            raise ValueError('End time cannot be before start time')
        return self


class PositionData(BaseModel):
    """포지션 데이터 검증 모델"""

    symbol: str = Field(..., pattern=r'^[A-Z0-9]{2,20}$')
    quantity: float = Field(..., gt=0, description="포지션 수량")
    entry_price: float = Field(..., gt=0, description="진입 가격")
    stop_price: float = Field(..., gt=0, description="스탑 가격")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode='after')
    def validate_stop_price(self):
        """스탑 가격이 진입 가격보다 낮은지 검증 (롱 포지션 가정)"""
        if self.stop_price >= self.entry_price:
            raise ValueError('Stop price should be below entry price for long positions')
        return self


class OrderData(BaseModel):
    """주문 데이터 검증 모델"""

    symbol: str = Field(..., pattern=r'^[A-Z0-9]{2,20}$')
    side: str = Field(..., pattern=r'^(BUY|SELL)$')
    type: str = Field(..., pattern=r'^(MARKET|LIMIT|STOP_LOSS|TRAILING_STOP)$')
    quantity: Optional[float] = Field(None, gt=0)
    quote_order_qty: Optional[float] = Field(None, gt=0)
    price: Optional[float] = Field(None, gt=0)
    stop_price: Optional[float] = Field(None, gt=0)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode='after')
    def validate_order_requirements(self):
        """주문 유형별 필수 필드 검증"""
        if self.type == 'MARKET':
            if self.side == 'BUY' and not self.quote_order_qty:
                raise ValueError('MARKET BUY orders require quoteOrderQty')
            elif self.side == 'SELL' and not self.quantity:
                raise ValueError('MARKET SELL orders require quantity')
        elif self.type == 'LIMIT':
            if not self.price or not self.quantity:
                raise ValueError('LIMIT orders require both price and quantity')
        elif self.type in ['STOP_LOSS', 'TRAILING_STOP']:
            if not self.stop_price:
                raise ValueError('STOP_LOSS and TRAILING_STOP orders require stopPrice')

        return self


class StrategyConfig(BaseModel):
    """전략 설정 검증 모델"""

    strategy_name: str = Field(..., min_length=1)
    symbol: str = Field(..., pattern=r'^[A-Z0-9]{2,20}$')
    timeframe: str = Field(..., pattern=r'^[0-9]+[smhd]$')

    # ATR Trailing Stop Strategy
    atr_period: Optional[int] = Field(14, ge=1, le=100)
    atr_multiplier: Optional[float] = Field(0.5, gt=0, le=10)

    # Composite Strategy
    ema_fast: Optional[int] = Field(12, ge=2, le=200)
    ema_slow: Optional[int] = Field(26, ge=2, le=200)
    rsi_length: Optional[int] = Field(14, ge=2, le=100)
    bb_length: Optional[int] = Field(20, ge=5, le=100)

    # Risk Management
    risk_per_trade: Optional[float] = Field(0.005, gt=0, le=0.1)
    max_position_size: Optional[float] = Field(0.2, gt=0, le=1.0)

    model_config = ConfigDict(
        extra="allow"  # 알 수 없는 필드도 허용
    )


def validate_kline_data(raw_data: List[List]) -> List[NormalizedKlineData]:
    """
    Raw Kline 데이터를 검증하고 정규화

    Args:
        raw_data: 바이낸스 API에서 받은 원시 Kline 데이터

    Returns:
        검증된 NormalizedKlineData 리스트

    Raises:
        ValidationError: 데이터 검증 실패 시
    """
    validated_data = []

    for i, kline in enumerate(raw_data):
        try:
            # Raw 데이터 변환
            kline_dict = {
                "open_time": datetime.fromtimestamp(kline[0] / 1000, tz=timezone.utc),
                "open_price": Decimal(str(kline[1])),
                "high_price": Decimal(str(kline[2])),
                "low_price": Decimal(str(kline[3])),
                "close_price": Decimal(str(kline[4])),
                "volume": Decimal(str(kline[5])),
                "close_time": datetime.fromtimestamp(kline[6] / 1000, tz=timezone.utc),
                "quote_asset_volume": Decimal(str(kline[7])),
                "number_of_trades": int(kline[8]),
                "taker_buy_base_asset_volume": Decimal(str(kline[9])),
                "taker_buy_quote_asset_volume": Decimal(str(kline[10])),
                "ignore": kline[11] if len(kline) > 11 else None
            }

            # KlineData로 검증
            kline_data = KlineData(**kline_dict)

            # NormalizedKlineData로 변환
            normalized = NormalizedKlineData(
                open_time=kline_data.open_time,
                open=float(kline_data.open_price),
                high=float(kline_data.high_price),
                low=float(kline_data.low_price),
                close=float(kline_data.close_price),
                volume=float(kline_data.volume)
            )

            validated_data.append(normalized)

        except Exception as e:
            raise ValidationError(
                message=f"Invalid kline data at index {i}",
                field=f"kline[{i}]",
                value=str(kline),
                context={"error": str(e)}
            )

    return validated_data


def validate_position_data(data: Dict[str, Any]) -> PositionData:
    """
    포지션 데이터를 검증

    Args:
        data: 포지션 데이터 딕셔너리

    Returns:
        검증된 PositionData

    Raises:
        ValidationError: 데이터 검증 실패 시
    """
    try:
        return PositionData(**data)
    except Exception as e:
        raise ValidationError(
            message="Invalid position data",
            field="position",
            value=str(data),
            context={"error": str(e)}
        )
