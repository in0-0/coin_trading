"""
TradingEngine: 거래 로직을 조율하는 메인 엔진

TDD: TradingEngine 클래스 구현
"""
import logging
import time
import signal
from typing import Dict, Optional, Callable, Any
from datetime import datetime

from core.configuration import Configuration
from core.exceptions import TradingError, OrderError, DataError
from core.signal import TradingSignal, SignalType, SignalAction
from models import Position, Signal
from trader.order_manager import OrderManager
from trader.position_manager import PositionManager
from binance_data import BinanceData
from strategy_factory import StrategyFactory
from state_manager import StateManager


class TradingEngine:
    """
    거래 로직을 조율하는 메인 엔진

    전략 실행, 포지션 관리, 주문 실행을 통합적으로 관리합니다.
    """

    def __init__(
        self,
        config: Configuration,
        order_manager: OrderManager,
        position_manager: PositionManager,
        strategy_factory: StrategyFactory,
        data_provider: BinanceData
    ):
        """
        Args:
            config: 거래 설정
            order_manager: 주문 관리자
            position_manager: 포지션 관리자
            strategy_factory: 전략 팩토리
            data_provider: 데이터 제공자
        """
        self.config = config
        self.order_manager = order_manager
        self.position_manager = position_manager
        self.strategy_factory = strategy_factory
        self.data_provider = data_provider

        # 실행 상태 관리
        self._running = False
        self._shutdown_requested = False

        # 상태 관리자 초기화
        self.state_manager = StateManager("live_positions.json")

        # 전략들 초기화
        self.strategies = {
            symbol: self._setup_strategy(symbol) for symbol in config.symbols
        }

        # 포지션들 로드
        self.positions: Dict[str, Position] = self.state_manager.load_positions()
        logging.info(f"초기 포지션 로드: {len(self.positions)}개")

    def _setup_strategy(self, symbol: str):
        """심볼별 전략 설정"""
        if self.config.strategy_name == "composite_signal":
            # 복합 전략 설정 (기존 코드와 유사)
            from types import SimpleNamespace
            from trader.symbol_rules import resolve_composite_params

            config = SimpleNamespace(
                ema_fast=12, ema_slow=26, bb_len=20, rsi_len=14,
                macd_fast=12, macd_slow=26, macd_signal=9, atr_len=14,
                k_atr_norm=1.0, vol_len=20, obv_span=20, max_score=1.0,
                buy_threshold=0.3, sell_threshold=-0.3,
                weights=SimpleNamespace(ma=0.25, bb=0.15, rsi=0.15, macd=0.25, vol=0.1, obv=0.1)
            )

            resolved = resolve_composite_params(symbol, self.config.execution_timeframe, config)
            return self.strategy_factory.create_strategy("composite_signal", config=resolved)
        else:
            # 기본 ATR 전략
            return self.strategy_factory.create_strategy(
                "atr_trailing_stop",
                symbol=symbol,
                atr_multiplier=self.config.atr_multiplier,
                risk_per_trade=self.config.risk_per_trade
            )

    def run(self) -> None:
        """메인 거래 루프 실행"""
        logging.info("거래 엔진 시작")
        self._running = True

        # 종료 시그널 핸들러 설정
        def shutdown_handler(signum, frame):
            logging.warning("종료 시그널 수신, 안전하게 종료합니다...")
            self._shutdown_requested = True

        signal.signal(signal.SIGINT, shutdown_handler)
        signal.signal(signal.SIGTERM, shutdown_handler)

        try:
            while self._running and not self._shutdown_requested:
                try:
                    self._execute_trading_cycle()
                    time.sleep(self.config.execution_interval)
                except Exception as e:
                    logging.exception(f"거래 사이클 실행 중 오류: {e}")
                    time.sleep(5)  # 오류 발생 시 잠시 대기

            self._shutdown()

        except Exception as e:
            logging.exception(f"거래 엔진 치명적 오류: {e}")
            self._emergency_shutdown()

    def stop(self) -> None:
        """거래 엔진 중지 요청"""
        self._running = False
        logging.info("거래 엔진 중지 요청됨")

    def shutdown(self) -> None:
        """거래 엔진 종료 처리"""
        logging.info("거래 엔진 종료 처리 시작")
        try:
            self._shutdown()
        except Exception as e:
            logging.error(f"종료 처리 중 오류: {e}")
            self._emergency_shutdown()

    def _execute_trading_cycle(self) -> None:
        """단일 거래 사이클 실행"""
        try:
            # 1. 스톱 로스 확인
            self._check_stop_losses()

            # 2. 잔고 확인
            usdt_balance = self._get_usdt_balance()
            if usdt_balance <= self.config.min_order_usdt:
                return

            # 3. 동시 포지션 수 확인
            if len(self.positions) >= self.config.max_concurrent_positions:
                return

            # 4. 각 심볼에 대한 전략 실행
            for symbol in self.config.symbols:
                if symbol in self.positions:  # 이미 포지션 보유 중
                    continue

                try:
                    self._execute_strategy_for_symbol(symbol)
                except Exception as e:
                    logging.error(f"{symbol} 전략 실행 중 오류: {e}")
                    continue

        except Exception as e:
            logging.exception(f"거래 사이클 실행 중 오류: {e}")
            raise

    def _execute_strategy_for_symbol(self, symbol: str) -> None:
        """특정 심볼에 대한 전략 실행"""
        try:
            # 시장 데이터 조회
            market_data = self.data_provider.get_and_update_klines(
                symbol, self.config.execution_timeframe
            )

            if market_data is None or market_data.empty:
                logging.warning(f"{symbol}: 시장 데이터 조회 실패")
                return

            # 현재 포지션 조회
            current_position = self.positions.get(symbol)

            # 전략 실행
            strategy = self.strategies[symbol]

            # 기존 Signal Enum을 사용하는 전략의 경우
            if hasattr(strategy, 'get_signal'):
                signal = strategy.get_signal(market_data, current_position)

                # 기존 Signal을 TradingSignal로 변환
                trading_signal = self._convert_legacy_signal(signal, market_data)

            # 새로운 TradingSignal을 직접 반환하는 전략의 경우
            elif hasattr(strategy, 'get_trading_signal'):
                trading_signal = strategy.get_trading_signal(market_data, current_position)
            else:
                logging.warning(f"{symbol}: 적절한 신호 메서드를 찾을 수 없습니다")
                return

            # 신호 처리
            self._process_trading_signal(symbol, trading_signal, market_data)

        except Exception as e:
            logging.error(f"{symbol} 전략 실행 중 오류: {e}")
            raise TradingError(f"전략 실행 실패: {symbol}", context={"error": str(e)}) from e

    def _convert_legacy_signal(self, legacy_signal: Signal, market_data) -> TradingSignal:
        """기존 Signal Enum을 TradingSignal로 변환"""
        try:
            # 신호 변환
            if legacy_signal == Signal.HOLD:
                return TradingSignal(SignalType.HOLD, SignalAction.EXIT)
            elif legacy_signal == Signal.BUY:
                return TradingSignal(SignalType.BUY, SignalAction.ENTRY)
            elif legacy_signal == Signal.SELL:
                return TradingSignal(SignalType.SELL, SignalAction.EXIT)
            elif legacy_signal == Signal.BUY_NEW:
                return TradingSignal(SignalType.BUY, SignalAction.ENTRY)
            elif legacy_signal == Signal.BUY_ADD:
                return TradingSignal(SignalType.BUY, SignalAction.ADD)
            elif legacy_signal == Signal.SELL_PARTIAL:
                return TradingSignal(SignalType.SELL, SignalAction.PARTIAL_EXIT)
            elif legacy_signal == Signal.SELL_ALL:
                return TradingSignal(SignalType.SELL, SignalAction.EXIT)
            elif legacy_signal == Signal.UPDATE_TRAIL:
                return TradingSignal(SignalType.SELL, SignalAction.STOP_UPDATE)
            else:
                return TradingSignal(SignalType.HOLD, SignalAction.EXIT)

        except Exception as e:
            logging.error(f"기존 Signal 변환 중 오류: {e}")
            return TradingSignal(SignalType.HOLD, SignalAction.EXIT)

    def _process_trading_signal(self, symbol: str, signal: TradingSignal, market_data) -> None:
        """거래 신호 처리"""
        try:
            if signal.is_buy and signal.is_entry:
                # 매수 진입 신호
                usdt_balance = self._get_usdt_balance()
                spend_amount = self._calculate_position_size(symbol, usdt_balance, market_data, signal)

                if spend_amount and spend_amount >= self.config.min_order_usdt:
                    score_meta = {
                        "confidence": signal.confidence,
                        **(signal.metadata or {})
                    }

                    position = self.order_manager.place_buy_order(
                        symbol=symbol,
                        usdt_amount=spend_amount,
                        positions=self.positions,
                        score_meta=score_meta
                    )

                    if position:
                        logging.info(f"매수 주문 성공: {symbol}, 금액: {spend_amount}")
                    else:
                        logging.warning(f"매수 주문 실패: {symbol}")

            elif signal.is_sell and signal.is_exit:
                # 매도 청산 신호
                success = self.order_manager.place_sell_order(symbol, self.positions)
                if success:
                    logging.info(f"매도 주문 성공: {symbol}")

            elif signal.is_sell and signal.is_partial_exit:
                # 부분 청산 신호
                if symbol in self.positions:
                    position = self.positions[symbol]
                    # 부분 청산 수량 계산 (현재는 전체 수량의 50%)
                    exit_qty = position.qty * 0.5

                    success = self.order_manager.place_sell_order(
                        symbol, self.positions, partial_exit=True, exit_qty=exit_qty
                    )
                    if success:
                        logging.info(f"부분 청산 성공: {symbol}, 수량: {exit_qty}")

            elif signal.is_sell and signal.is_stop_update:
                # 스톱 업데이트 신호
                if symbol in self.positions:
                    position = self.positions[symbol]
                    # 현재가 기준으로 새로운 스톱 가격 계산 (간단한 구현)
                    current_price = market_data['Close'].iloc[-1]
                    new_stop_price = current_price * 0.95  # 5% 손실 시 스톱

                    self.order_manager.update_trailing_stop(symbol, position, new_stop_price)

        except Exception as e:
            logging.error(f"{symbol} 신호 처리 중 오류: {e}")
            raise TradingError(f"신호 처리 실패: {symbol}", context={"signal": str(signal)}) from e

    def _calculate_position_size(self, symbol: str, usdt_balance: float, market_data, signal: TradingSignal) -> Optional[float]:
        """포지션 사이즈 계산"""
        try:
            # 간단한 포지션 사이징 (현재 잔고의 10%)
            max_position_size = usdt_balance * self.config.max_symbol_weight

            # 신호의 신뢰도에 따른 조정
            confidence_multiplier = max(0.1, signal.confidence)  # 최소 10%

            position_size = max_position_size * confidence_multiplier

            return min(position_size, max_position_size)

        except Exception as e:
            logging.error(f"포지션 사이즈 계산 중 오류: {symbol}: {e}")
            return None

    def _check_stop_losses(self) -> None:
        """스톱 로스 확인 및 실행"""
        for symbol, position in list(self.positions.items()):
            try:
                # 현재가 조회 (간단한 구현)
                current_price = self.data_provider.get_current_price(symbol)

                if current_price <= 0:
                    continue

                # 스톱 가격 확인
                if current_price <= position.stop_price:
                    logging.info(f"스톱 로스 트리거: {symbol}, 가격: {current_price}, 스톱: {position.stop_price}")

                    # 매도 주문 실행
                    success = self.order_manager.place_sell_order(symbol, self.positions)
                    if success:
                        logging.info(f"스톱 로스 매도 성공: {symbol}")

            except Exception as e:
                logging.error(f"{symbol} 스톱 로스 확인 중 오류: {e}")

    def _get_usdt_balance(self) -> float:
        """USDT 잔고 조회"""
        try:
            # 실제 잔고 조회는 TradeExecutor를 통해 수행해야 함
            # 현재는 간단한 구현
            return 10000.0  # 테스트용 기본값
        except Exception as e:
            logging.error(f"잔고 조회 중 오류: {e}")
            return 0.0

    def _shutdown(self) -> None:
        """정상 종료 처리"""
        logging.info("거래 엔진 종료 중...")

        try:
            # 모든 포지션 정리
            for symbol in list(self.positions.keys()):
                try:
                    success = self.order_manager.place_sell_order(symbol, self.positions)
                    if success:
                        logging.info(f"포지션 정리 완료: {symbol}")
                except Exception as e:
                    logging.error(f"포지션 정리 실패: {symbol}: {e}")

            logging.info("거래 엔진 정상 종료 완료")

        except Exception as e:
            logging.exception(f"종료 처리 중 오류: {e}")

    def _emergency_shutdown(self) -> None:
        """비상 종료 처리"""
        logging.error("거래 엔진 비상 종료")

        # 비상 시에도 포지션 정리 시도
        try:
            self._shutdown()
        except Exception:
            pass

        # 강제 종료
        logging.critical("비상 종료 완료")
