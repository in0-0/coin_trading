"""
SimulatedOrderExecutor: 시뮬레이션 모드 주문 실행

TDD: SimulatedOrderExecutor 클래스 구현
"""
import logging
from typing import Dict, Optional, Any
from datetime import datetime

from binance.client import Client
from core.configuration import Configuration
from core.exceptions import OrderError
from models import Position
from binance_data import BinanceData
from .order_execution_template import OrderExecutionTemplate


class SimulatedOrderExecutor(OrderExecutionTemplate):
    """
    시뮬레이션 모드 주문 실행

    실제 API 호출 없이 시뮬레이션된 주문 결과를 반환합니다.
    """

    def __init__(self, client: Client, config: Configuration, data_provider: BinanceData):
        """
        Args:
            client: Binance 클라이언트 (시뮬레이션에서는 사용하지 않음)
            config: 거래 설정
            data_provider: 데이터 제공자
        """
        super().__init__(client, config, data_provider)

    def do_buy_order(
        self,
        symbol: str,
        usdt_amount: float,
        positions: Dict[str, Position],
        score_meta: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        시뮬레이션 매수 주문 실행

        Args:
            symbol: 거래 심볼
            usdt_amount: 주문 금액
            positions: 현재 포지션들
            score_meta: 신호 메타데이터

        Returns:
            시뮬레이션된 주문 실행 결과
        """
        # 현재가 조회
        current_price = self.data_provider.get_current_price(symbol)
        if current_price <= 0:
            raise OrderError(f"현재가를 조회할 수 없습니다: {symbol}", symbol=symbol)

        # 수량 계산
        qty = usdt_amount / current_price

        # 시뮬레이션된 주문 결과 생성
        order_result = {
            "symbol": symbol,
            "orderId": f"sim-{int(datetime.now().timestamp())}",
            "clientOrderId": f"sim-buy-{symbol}-{int(datetime.now().timestamp())}",
            "transactTime": int(datetime.now().timestamp() * 1000),
            "price": str(current_price),
            "origQty": str(qty),
            "executedQty": str(qty),
            "cummulativeQuoteQty": str(usdt_amount),
            "status": "FILLED",
            "type": "MARKET",
            "side": "BUY",
            "fills": [
                {
                    "price": str(current_price),
                    "qty": str(qty),
                    "commission": "0.0",
                    "commissionAsset": symbol.replace("USDT", "")
                }
            ]
        }

        logging.info(f"🔄 시뮬레이션 매수 주문: {symbol} @ ${current_price:.4f}, 수량: {qty:.6f}")
        return order_result

    def do_sell_order(
        self,
        symbol: str,
        positions: Dict[str, Position],
        partial_exit: bool = False,
        exit_qty: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        시뮬레이션 매도 주문 실행

        Args:
            symbol: 거래 심볼
            positions: 현재 포지션들
            partial_exit: 부분 청산 여부
            exit_qty: 청산 수량

        Returns:
            시뮬레이션된 주문 실행 결과
        """
        if symbol not in positions:
            raise OrderError(f"매도할 포지션이 없습니다: {symbol}", symbol=symbol)

        position = positions[symbol]

        # 청산 수량 결정
        qty_to_sell = exit_qty if exit_qty else position.qty

        # 현재가 조회
        current_price = self.data_provider.get_current_price(symbol)
        if current_price <= 0:
            raise OrderError(f"현재가를 조회할 수 없습니다: {symbol}", symbol=symbol)

        # 총 매도 금액 계산
        sell_amount = qty_to_sell * current_price

        # PnL 계산
        pnl = (current_price - position.entry_price) * qty_to_sell

        # 부분 청산인 경우 포지션 업데이트
        if partial_exit and exit_qty:
            position.qty -= qty_to_sell
            if position.qty <= 0:
                del positions[symbol]  # 포지션 완전 청산
            else:
                positions[symbol] = position
        else:
            # 전량 청산
            del positions[symbol]

        # 시뮬레이션된 주문 결과 생성
        order_result = {
            "symbol": symbol,
            "orderId": f"sim-sell-{int(datetime.now().timestamp())}",
            "clientOrderId": f"sim-sell-{symbol}-{int(datetime.now().timestamp())}",
            "transactTime": int(datetime.now().timestamp() * 1000),
            "price": str(current_price),
            "origQty": str(qty_to_sell),
            "executedQty": str(qty_to_sell),
            "cummulativeQuoteQty": str(sell_amount),
            "status": "FILLED",
            "type": "MARKET",
            "side": "SELL",
            "fills": [
                {
                    "price": str(current_price),
                    "qty": str(qty_to_sell),
                    "commission": "0.0",
                    "commissionAsset": "USDT"
                }
            ]
        }

        # PnL 정보 추가
        order_result["pnl"] = pnl
        order_result["pnl_pct"] = (current_price / position.entry_price - 1.0) * 100

        # 로그 메시지 생성
        log_msg = f"🛑 시뮬레이션 매도 주문: {symbol} @ ${current_price:.4f}"
        if partial_exit:
            log_msg += f" (부분 청산, 수량: {qty_to_sell:.6f})"
        else:
            log_msg += f" (전량 청산, 수량: {qty_to_sell:.6f})"
        log_msg += f"\nPnL: ${pnl:.2f} ({order_result['pnl_pct']:.2f}%)"
        logging.info(log_msg)

        return order_result

    def handle_execution_error(self, symbol: str, error: Exception, order_type: str) -> None:
        """
        시뮬레이션 모드에서의 오류 처리

        Args:
            symbol: 거래 심볼
            error: 발생한 오류
            order_type: 주문 타입 ("BUY" 또는 "SELL")
        """
        # 시뮬레이션 모드에서는 실제 API 호출이 없으므로
        # 대부분의 오류는 발생하지 않지만, 만약 발생하면
        # 자세한 정보와 함께 로깅
        logging.error(f"시뮬레이션 {order_type} 주문 오류: {symbol}: {error}")

        # 기본 오류 처리 호출
        super().handle_execution_error(symbol, error, order_type)
