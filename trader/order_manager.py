"""
OrderManager: 주문 실행 및 검증을 담당하는 클래스

TDD: OrderManager 클래스 구현
"""
import logging
from typing import Dict, Optional, Any
from datetime import datetime

from core.configuration import Configuration
from core.constants import TradingConstants
from core.exceptions import OrderError, ValidationError, ConfigurationError
from models import Position
from trader.trade_executor import TradeExecutor


class OrderManager:
    """
    주문 실행과 검증을 담당하는 클래스

    TradeExecutor를 사용하여 실제 주문을 실행하고,
    주문 전/후 검증을 수행합니다.
    """

    def __init__(self, trade_executor: TradeExecutor, config: Configuration):
        """
        Args:
            trade_executor: 주문 실행을 담당하는 TradeExecutor
            config: 거래 설정
        """
        self.trade_executor = trade_executor
        self.config = config

    def place_buy_order(
        self,
        symbol: str,
        usdt_amount: float,
        positions: Dict[str, Position],
        score_meta: Optional[Dict[str, Any]] = None
    ) -> Optional[Position]:
        """
        매수 주문을 실행합니다.

        Args:
            symbol: 거래 심볼 (예: 'BTCUSDT')
            usdt_amount: 주문 금액 (USDT)
            positions: 현재 포지션들
            score_meta: 신호 관련 메타데이터

        Returns:
            생성된 Position 객체 또는 None (실패 시)

        Raises:
            OrderError: 주문 실행 실패 시
            ValidationError: 주문 파라미터 검증 실패 시
        """
        try:
            # 주문 전 검증
            self._validate_buy_order(symbol, usdt_amount)

            # 주문 실행
            self.trade_executor.market_buy(
                symbol=symbol,
                usdt_to_spend=usdt_amount,
                positions=positions,
                atr_multiplier=self.config.atr_multiplier,
                timeframe=self.config.execution_timeframe,
                k_sl=self.config.bracket_k_sl,
                rr=self.config.bracket_rr,
                score_meta=score_meta or {}
            )

            # 주문 성공 시 새로운 포지션 반환
            return positions.get(symbol)

        except Exception as e:
            error_msg = f"매수 주문 실패: {symbol}, 금액: {usdt_amount}"
            logging.error(f"{error_msg}: {e}")
            raise OrderError(error_msg, symbol=symbol, context={"amount": usdt_amount}) from e

    def place_sell_order(
        self,
        symbol: str,
        positions: Dict[str, Position],
        partial_exit: bool = False,
        exit_qty: Optional[float] = None
    ) -> bool:
        """
        매도 주문을 실행합니다.

        Args:
            symbol: 거래 심볼
            positions: 현재 포지션들
            partial_exit: 부분 청산 여부
            exit_qty: 청산 수량 (부분 청산 시)

        Returns:
            주문 성공 여부

        Raises:
            OrderError: 주문 실행 실패 시
            ValidationError: 주문 파라미터 검증 실패 시
        """
        try:
            # 포지션 존재 확인
            if symbol not in positions:
                raise ValidationError(f"매도할 포지션이 없습니다: {symbol}", symbol=symbol)

            position = positions[symbol]

            # 부분 청산의 경우 수량 검증
            if partial_exit and exit_qty:
                self._validate_partial_exit(position, exit_qty)

            # 주문 실행
            if partial_exit and exit_qty:
                # 부분 청산 실행
                self.trade_executor.market_sell_partial(
                    symbol=symbol,
                    position=position,
                    qty=exit_qty,
                    metadata={"partial_exit": True}
                )
            else:
                # 전량 청산 실행
                self.trade_executor.market_sell(symbol, positions)

            return True

        except Exception as e:
            error_msg = f"매도 주문 실패: {symbol}"
            logging.error(f"{error_msg}: {e}")
            raise OrderError(error_msg, symbol=symbol) from e

    def update_trailing_stop(
        self,
        symbol: str,
        position: Position,
        new_stop_price: float
    ) -> bool:
        """
        트레일링 스톱을 업데이트합니다.

        Args:
            symbol: 거래 심볼
            position: 업데이트할 포지션
            new_stop_price: 새로운 스톱 가격

        Returns:
            업데이트 성공 여부

        Raises:
            ValidationError: 스톱 가격 검증 실패 시
            OrderError: 업데이트 실패 시
        """
        try:
            # 스톱 가격 검증
            self._validate_stop_price(position, new_stop_price)

            # 포지션의 트레일링 스톱 업데이트
            position.update_trailing_stop(new_stop_price)

            logging.info(f"트레일링 스톱 업데이트: {symbol}, {position.trailing_stop_price} -> {new_stop_price}")
            return True

        except Exception as e:
            error_msg = f"트레일링 스톱 업데이트 실패: {symbol}"
            logging.error(f"{error_msg}: {e}")
            raise OrderError(error_msg, symbol=symbol) from e

    def _validate_buy_order(self, symbol: str, usdt_amount: float) -> None:
        """
        매수 주문의 유효성을 검증합니다.

        Args:
            symbol: 거래 심볼
            usdt_amount: 주문 금액

        Raises:
            ValidationError: 검증 실패 시
        """
        # 최소 주문 금액 검증
        if usdt_amount < self.config.min_order_usdt:
            raise ValidationError(
                f"주문 금액이 최소 주문 금액보다 작습니다",
                field="usdt_amount",
                value=usdt_amount,
                constraint=f"minimum: {self.config.min_order_usdt}"
            )

        # 최대 심볼 비중 검증
        if usdt_amount > self.config.max_symbol_weight * 1000000:  # 대략적인 계산
            raise ValidationError(
                f"주문 금액이 최대 심볼 비중을 초과합니다",
                field="usdt_amount",
                value=usdt_amount,
                constraint=f"maximum: {self.config.max_symbol_weight * 1000000}"
            )

        # 설정 유효성 검증
        if not self.config.validate():
            raise ConfigurationError("거래 설정이 유효하지 않습니다")

    def _validate_partial_exit(self, position: Position, exit_qty: float) -> None:
        """
        부분 청산의 유효성을 검증합니다.

        Args:
            position: 청산할 포지션
            exit_qty: 청산 수량

        Raises:
            ValidationError: 검증 실패 시
        """
        # 보유 수량보다 청산 수량이 많은지 확인
        if exit_qty > position.qty:
            raise ValidationError(
                "청산 수량이 보유 수량을 초과합니다",
                field="exit_qty",
                value=exit_qty,
                constraint=f"maximum: {position.qty}"
            )

        # 최소 주문 수량 확인 (현재가는 알 수 없으므로 대략적인 검증)
        min_qty_usdt = self.config.min_order_usdt
        if exit_qty < min_qty_usdt:  # 대략적인 검증
            raise ValidationError(
                "청산 수량이 너무 적습니다",
                field="exit_qty",
                value=exit_qty,
                constraint=f"minimum: {min_qty_usdt}"
            )

    def _validate_stop_price(self, position: Position, new_stop_price: float) -> None:
        """
        스톱 가격의 유효성을 검증합니다.

        Args:
            position: 포지션
            new_stop_price: 새로운 스톱 가격

        Raises:
            ValidationError: 검증 실패 시
        """
        # 스톱 가격이 현재가보다 높은지 확인 (롱 포지션의 경우)
        # 실제 현재가는 알 수 없으므로 기본 검증만 수행
        if new_stop_price <= 0:
            raise ValidationError(
                "스톱 가격이 유효하지 않습니다",
                field="stop_price",
                value=new_stop_price,
                constraint="must be positive"
            )

        # 스톱 가격이 진입가보다 높은지 확인 (의미있는 스톱이 되도록)
        if position.entry_price > 0 and new_stop_price >= position.entry_price:
            raise ValidationError(
                "스톱 가격이 진입가보다 높거나 같습니다",
                field="stop_price",
                value=new_stop_price,
                constraint=f"must be less than entry price: {position.entry_price}"
            )

    def get_order_status(self, symbol: str, order_id: str) -> Optional[Dict[str, Any]]:
        """
        주문 상태를 조회합니다.

        Args:
            symbol: 거래 심볼
            order_id: 주문 ID

        Returns:
            주문 상태 정보 또는 None
        """
        # 실제 구현에서는 TradeExecutor를 통해 상태 조회
        # 현재는 간단한 구현
        try:
            # TradeExecutor의 상태 조회 메서드를 호출해야 함
            # 현재는 None 반환
            return None
        except Exception as e:
            logging.error(f"주문 상태 조회 실패: {symbol}, {order_id}: {e}")
            return None
