"""
LiveOrderExecutor: 실제 Binance API를 통한 주문 실행

TDD: LiveOrderExecutor 클래스 구현
"""
import logging
import time
import random
from typing import Dict, Optional, Any

from binance.client import Client
from core.configuration import Configuration
from core.exceptions import OrderError
from models import Position
from binance_data import BinanceData
from .order_execution_template import OrderExecutionTemplate
from .symbol_rules import get_symbol_filters, round_qty_to_step, validate_min_notional


class LiveOrderExecutor(OrderExecutionTemplate):
    """
    실제 Binance API를 통한 주문 실행

    Template Method 패턴을 상속받아 실제 API 호출을 구현합니다.
    """

    def __init__(self, client: Client, config: Configuration, data_provider: BinanceData):
        """
        Args:
            client: Binance 클라이언트
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
        실제 Binance API를 통한 매수 주문 실행

        Args:
            symbol: 거래 심볼
            usdt_amount: 주문 금액
            positions: 현재 포지션들
            score_meta: 신호 메타데이터

        Returns:
            주문 실행 결과
        """
        client_order_id = self._generate_client_order_id("buy", symbol)

        def _place_order() -> Dict[str, Any]:
            """실제 주문 생성"""
            return self.client.create_order(
                symbol=symbol,
                side="BUY",
                type="MARKET",
                quoteOrderQty=round(usdt_amount, 2),
                newOrderRespType="FULL",
                newClientOrderId=client_order_id,
            )

        # 재시도 로직을 포함한 주문 실행
        resp = self._execute_with_retries(symbol, client_order_id, _place_order)

        if not resp:
            raise OrderError(f"매수 주문 응답 없음: {symbol}", symbol=symbol)

        # 체결 대기
        if str(resp.get("status", "")).upper() != "FILLED":
            resp = self._wait_for_execution(symbol, resp)

        return resp

    def do_sell_order(
        self,
        symbol: str,
        positions: Dict[str, Position],
        partial_exit: bool = False,
        exit_qty: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        실제 Binance API를 통한 매도 주문 실행

        Args:
            symbol: 거래 심볼
            positions: 현재 포지션들
            partial_exit: 부분 청산 여부
            exit_qty: 청산 수량

        Returns:
            주문 실행 결과
        """
        if symbol not in positions:
            raise OrderError(f"매도할 포지션이 없습니다: {symbol}", symbol=symbol)

        position = positions[symbol]

        # 수량 계산 및 검증
        qty_to_sell = exit_qty if exit_qty else position.qty

        # 심볼 규칙에 따른 수량 조정
        filters = get_symbol_filters(self.client, symbol, {})
        qty_rounded = round_qty_to_step(qty_to_sell, filters.lot_step_size)

        if qty_rounded <= 0 or qty_rounded < filters.lot_min_qty:
            raise OrderError(
                f"수량이 최소 기준에 미달합니다: {qty_rounded} < {filters.lot_min_qty}",
                symbol=symbol
            )

        # 주문금액 검증
        current_price = self.data_provider.get_current_price(symbol)
        if not validate_min_notional(current_price, qty_rounded, filters.min_notional):
            raise OrderError(
                f"주문금액이 최소 기준에 미달합니다: {current_price * qty_rounded} < {filters.min_notional}",
                symbol=symbol
            )

        client_order_id = self._generate_client_order_id("sell", symbol)

        def _place_order() -> Dict[str, Any]:
            """실제 매도 주문 생성"""
            return self.client.create_order(
                symbol=symbol,
                side="SELL",
                type="MARKET",
                quantity=qty_rounded,
                newOrderRespType="FULL",
                newClientOrderId=client_order_id,
            )

        # 재시도 로직을 포함한 주문 실행
        resp = self._execute_with_retries(symbol, client_order_id, _place_order)

        if not resp:
            raise OrderError(f"매도 주문 응답 없음: {symbol}", symbol=symbol)

        # 체결 대기
        if str(resp.get("status", "")).upper() != "FILLED":
            resp = self._wait_for_execution(symbol, resp)

        # 부분 청산인 경우 포지션 업데이트
        if partial_exit and exit_qty:
            executed_qty = float(resp.get("executedQty", 0.0))
            position.qty -= executed_qty
            if position.qty <= 0:
                del positions[symbol]  # 포지션 완전 청산
            else:
                positions[symbol] = position

        return resp

    def _execute_with_retries(self, symbol: str, client_order_id: str, place_order_fn) -> Optional[Dict[str, Any]]:
        """
        재시도 로직을 포함한 주문 실행

        Args:
            symbol: 거래 심볼
            client_order_id: 클라이언트 주문 ID
            place_order_fn: 주문 생성 함수

        Returns:
            주문 실행 결과 또는 None
        """
        retries = max(0, self.config.order_retry)
        delay = 0.5

        for attempt in range(retries + 1):
            try:
                resp = place_order_fn()
                if resp:
                    return resp
            except Exception as exc:
                logging.warning(f"{symbol} 주문 시도 {attempt + 1} 실패: {exc}")

                # 기존 주문 조회 시도
                try:
                    orders = self.client.get_all_orders(symbol=symbol, limit=5)
                    for order in orders or []:
                        if order.get("clientOrderId") == client_order_id:
                            return order
                except Exception:
                    pass

            if attempt < retries:
                time.sleep(delay + random.random() * 0.2)
                delay = min(2.0, delay * 1.5)

        return None

    def _wait_for_execution(self, symbol: str, initial_resp: Dict[str, Any]) -> Dict[str, Any]:
        """
        주문 체결을 기다림

        Args:
            symbol: 거래 심볼
            initial_resp: 초기 주문 응답

        Returns:
            체결된 주문 정보
        """
        try:
            order_id = initial_resp.get("orderId")
            client_order_id = initial_resp.get("clientOrderId") or initial_resp.get("origClientOrderId")
            timeout_sec = self.config.order_timeout_sec
            deadline = time.time() + timeout_sec
            last_resp = initial_resp

            while time.time() < deadline:
                try:
                    if order_id:
                        last_resp = self.client.get_order(symbol=symbol, orderId=order_id)
                    elif client_order_id:
                        last_resp = self.client.get_order(symbol=symbol, origClientOrderId=client_order_id)

                    if str(last_resp.get("status", "")).upper() == "FILLED":
                        return last_resp
                except Exception:
                    pass

                time.sleep(0.5)

            return last_resp
        except Exception:
            return initial_resp

    def _generate_client_order_id(self, side: str, symbol: str) -> str:
        """클라이언트 주문 ID 생성"""
        base = f"gptbot-{side}-{symbol.lower()}"
        suffix = f"-{int(time.time()*1000)}-{random.randint(100,999)}"
        return base + suffix
