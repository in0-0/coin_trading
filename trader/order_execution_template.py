"""
OrderExecutionTemplate: 주문 실행을 위한 Template Method 패턴

TDD: OrderExecutionTemplate 추상 클래스 구현
"""
import logging
import time
import random
from abc import ABC, abstractmethod
from typing import Dict, Optional, Any, Tuple

from binance.client import Client
from core.dependency_injection import get_config
from core.exceptions import OrderError, ValidationError
from models import Position
from binance_data import BinanceData
from .symbol_rules import get_symbol_filters, round_qty_to_step, validate_min_notional
from .risk_manager import compute_initial_bracket


class OrderExecutionTemplate(ABC):
    """
    주문 실행을 위한 Template Method 패턴 추상 클래스

    LIVE와 SIMULATED 모드 간의 공통 알고리즘을 정의하고,
    각 모드별로 다른 구현을 제공합니다.
    """

    def __init__(self, client: Client, config: Configuration, data_provider: BinanceData):
        """
        Args:
            client: Binance 클라이언트
            config: 거래 설정
            data_provider: 데이터 제공자
        """
        self.client = client
        self.config = config
        self.data_provider = data_provider

    def execute_buy_order(
        self,
        symbol: str,
        usdt_amount: float,
        positions: Dict[str, Position],
        score_meta: Optional[Dict[str, Any]] = None
    ) -> Optional[Position]:
        """
        매수 주문 실행을 위한 Template Method

        공통 알고리즘:
        1. 전처리 검증
        2. 실제 주문 실행 (서브클래스별 구현)
        3. 후처리 및 결과 반환
        """
        try:
            # 전처리: 공통 검증 로직
            self.pre_execution_check(symbol, usdt_amount)

            # 주문 실행: 서브클래스별 구현
            execution_result = self.do_buy_order(symbol, usdt_amount, positions, score_meta)

            # 후처리: 결과 처리 및 로깅
            return self.post_execution_process(symbol, execution_result, positions, score_meta)

        except Exception as e:
            # 오류 처리 후크
            self.handle_execution_error(symbol, e, "BUY")
            raise

    def execute_sell_order(
        self,
        symbol: str,
        positions: Dict[str, Position],
        partial_exit: bool = False,
        exit_qty: Optional[float] = None
    ) -> bool:
        """
        매도 주문 실행을 위한 Template Method

        공통 알고리즘:
        1. 전처리 검증
        2. 실제 주문 실행 (서브클래스별 구현)
        3. 후처리 및 결과 반환
        """
        try:
            # 전처리: 공통 검증 로직
            self.pre_execution_check(symbol, None, positions, partial_exit, exit_qty)

            # 주문 실행: 서브클래스별 구현
            execution_result = self.do_sell_order(symbol, positions, partial_exit, exit_qty)

            # 후처리: 결과 처리 및 로깅
            return self.post_execution_process(symbol, execution_result, positions)

        except Exception as e:
            # 오류 처리 후크
            self.handle_execution_error(symbol, e, "SELL")
            raise

    @abstractmethod
    def do_buy_order(
        self,
        symbol: str,
        usdt_amount: float,
        positions: Dict[str, Position],
        score_meta: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        매수 주문 실행 - 서브클래스별 구현

        Args:
            symbol: 거래 심볼
            usdt_amount: 주문 금액
            positions: 현재 포지션들
            score_meta: 신호 메타데이터

        Returns:
            주문 실행 결과
        """
        pass

    @abstractmethod
    def do_sell_order(
        self,
        symbol: str,
        positions: Dict[str, Position],
        partial_exit: bool = False,
        exit_qty: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        매도 주문 실행 - 서브클래스별 구현

        Args:
            symbol: 거래 심볼
            positions: 현재 포지션들
            partial_exit: 부분 청산 여부
            exit_qty: 청산 수량

        Returns:
            주문 실행 결과
        """
        pass

    def pre_execution_check(
        self,
        symbol: str,
        usdt_amount: Optional[float] = None,
        positions: Optional[Dict[str, Position]] = None,
        partial_exit: bool = False,
        exit_qty: Optional[float] = None
    ) -> None:
        """
        주문 전 공통 검증 로직

        Args:
            symbol: 거래 심볼
            usdt_amount: 주문 금액 (매수 시)
            positions: 현재 포지션들
            partial_exit: 부분 청산 여부
            exit_qty: 청산 수량 (부분 청산 시)
        """
        # 킬 스위치 확인
        if getattr(self.config, 'kill_switch', False) and self.config.order_execution == "LIVE":
            raise OrderError("킬 스위치 활성화 상태입니다", symbol=symbol)

        # 매수 주문 검증
        if usdt_amount is not None:
            self._validate_buy_amount(symbol, usdt_amount)

        # 매도 주문 검증
        if positions is not None and symbol in positions:
            if partial_exit and exit_qty:
                self._validate_partial_exit(positions[symbol], exit_qty)

        # 슬리피지 확인 (LIVE 모드에서만)
        if self.config.order_execution == "LIVE":
            self._check_slippage(symbol)

    def post_execution_process(
        self,
        symbol: str,
        execution_result: Dict[str, Any],
        positions: Dict[str, Position],
        score_meta: Optional[Dict[str, Any]] = None
    ) -> Optional[Position]:
        """
        주문 후 공통 처리 로직

        Args:
            symbol: 거래 심볼
            execution_result: 주문 실행 결과
            positions: 현재 포지션들
            score_meta: 신호 메타데이터

        Returns:
            새로 생성된 포지션 또는 None
        """
        # 주문 결과를 분석하여 체결 정보 추출
        fills = execution_result.get("fills", [])
        if not fills:
            # 일부 응답에서 직접 필드 사용
            executed_qty = float(execution_result.get("executedQty", 0.0))
            cummulative_quote = float(execution_result.get("cummulativeQuoteQty", 0.0))
            avg_price = cummulative_quote / executed_qty if executed_qty > 0 else 0.0
            order_id = execution_result.get("orderId")
        else:
            # fills 배열에서 계산
            total_quote = sum(float(f.get("price", 0.0)) * float(f.get("qty", 0.0)) for f in fills)
            total_base = sum(float(f.get("qty", 0.0)) for f in fills)
            avg_price = total_quote / total_base if total_base > 0 else 0.0
            order_id = execution_result.get("orderId")

        # 성공적인 체결 확인
        if avg_price <= 0 or (fills and total_base <= 0):
            logging.warning(f"주문 체결 실패 또는 수량 0: {symbol}")
            return None

        # ATR 기반 브래킷 계산
        market_data = self.data_provider.get_and_update_klines(symbol, self.config.execution_timeframe)
        if market_data is not None and not market_data.empty:
            latest_close = float(market_data["Close"].iloc[-1])
            atr = float(market_data["atr"].iloc[-1]) if "atr" in market_data.columns else latest_close * 0.02

            try:
                sl, tp = compute_initial_bracket(
                    entry=avg_price,
                    atr=atr,
                    side="long",
                    k_sl=self.config.bracket_k_sl,
                    rr=self.config.bracket_rr
                )
            except Exception:
                sl = max(0.0, latest_close - atr * self.config.atr_multiplier)
                tp = latest_close + atr * self.config.atr_multiplier
        else:
            # 데이터 없으면 기본값 사용
            sl = avg_price * 0.95  # 5% 손실
            tp = avg_price * 1.05  # 5% 수익

        # 새로운 포지션 생성 (매수인 경우)
        if symbol not in positions:
            position = Position(
                symbol=symbol,
                qty=total_base if fills else executed_qty,
                entry_price=avg_price,
                stop_price=sl
            )
            positions[symbol] = position

            # 로깅
            self._log_order_result(symbol, avg_price, total_base if fills else executed_qty, "BUY", score_meta, order_id, sl, tp, atr)
            return position

        return None

    def handle_execution_error(self, symbol: str, error: Exception, order_type: str) -> None:
        """
        주문 실행 오류 처리 후크

        Args:
            symbol: 거래 심볼
            error: 발생한 오류
            order_type: 주문 타입 ("BUY" 또는 "SELL")
        """
        logging.error(f"{order_type} 주문 실행 오류: {symbol}: {error}")

        # 기본적으로는 다시 발생시키되, 서브클래스에서 오버라이드 가능
        if isinstance(error, (OrderError, ValidationError)):
            raise  # 이미 처리된 예외는 그대로 전파
        else:
            raise OrderError(f"{order_type} 주문 실패: {symbol}", symbol=symbol) from error

    def _validate_buy_amount(self, symbol: str, usdt_amount: float) -> None:
        """매수 금액 검증"""
        if usdt_amount < self.config.min_order_usdt:
            raise ValidationError(
                f"주문 금액이 최소 주문 금액보다 작습니다: {usdt_amount} < {self.config.min_order_usdt}",
                field="usdt_amount",
                value=usdt_amount
            )

    def _validate_partial_exit(self, position: Position, exit_qty: float) -> None:
        """부분 청산 수량 검증"""
        if exit_qty > position.qty:
            raise ValidationError(
                f"청산 수량이 보유 수량을 초과합니다: {exit_qty} > {position.qty}",
                field="exit_qty",
                value=exit_qty
            )

    def _check_slippage(self, symbol: str) -> None:
        """슬리피지 확인 (LIVE 모드에서만)"""
        if self.config.order_execution != "LIVE":
            return

        try:
            tick = self.client.get_orderbook_ticker(symbol=symbol)
            bid = float(tick.get("bidPrice", 0.0))
            ask = float(tick.get("askPrice", 0.0))

            if bid <= 0 or ask <= 0:
                return

            mid = (bid + ask) / 2.0
            spread_bps = (ask - bid) / mid * 10000.0

            if spread_bps > self.config.max_slippage_bps:
                raise ValidationError(
                    f"스프레드가 최대 허용 슬리피지를 초과합니다: {spread_bps:.2f}bps > {self.config.max_slippage_bps}bps",
                    symbol=symbol
                )
        except Exception as e:
            logging.warning(f"슬리피지 확인 실패: {symbol}: {e}")
            # 슬리피지 확인 실패는 치명적이지 않으므로 계속 진행

    def _log_order_result(
        self,
        symbol: str,
        avg_price: float,
        executed_qty: float,
        order_type: str,
        score_meta: Optional[Dict[str, Any]],
        order_id: Optional[str],
        sl: float,
        tp: float,
        atr: float
    ) -> None:
        """주문 결과 로깅"""
        meta_parts = []
        if score_meta:
            s = score_meta.get("score")
            conf = score_meta.get("confidence")
            kf = score_meta.get("kelly_f")

            if isinstance(s, (int, float)):
                meta_parts.append(f"S={float(s):.3f}")
            if isinstance(conf, (int, float)):
                meta_parts.append(f"Conf={float(conf):.2f}")
            if isinstance(kf, (int, float)):
                meta_parts.append(f"f*={float(kf):.3f}")

        meta_str = f" {' '.join(meta_parts)}" if meta_parts else ""

        logging.info(
            f"✅ {order_type} {symbol} id={order_id}\n"
            f"Avg: ${avg_price:.4f} Qty: {executed_qty:.6f}\n"
            f"SL: ${sl:.4f} TP: ${tp:.4f}{meta_str} ATR=${atr:.4f}"
        )
