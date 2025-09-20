#!/usr/bin/env python3
"""
개선된 라이브 트레이더

주요 개선사항:
- 통일된 에러 처리 시스템 적용
- 의존성 주입 패턴 적용
- Pydantic 기반 데이터 검증
- Position 책임 분리
- 설정 중앙화
"""

import os
import time
import signal
import logging
from datetime import datetime, timezone
from typing import Dict, Optional, Callable

import requests
import pandas as pd
from binance.client import Client

# --- Import Improved Modules ---
from core.error_handler import ErrorHandler, get_global_error_handler
from core.dependency_injection import get_config, configure_dependencies
from core.exceptions import TradingError, ConfigurationError, DataError
from core.data_models import StrategyConfig, MarketDataSummary
from core.position_manager import PositionStateManager, PositionService
from binance_data_improved import ImprovedBinanceData
from improved_strategy_factory import StrategyFactory
from state_manager import StateManager
from models import Position, Signal
from trader import Notifier, PositionSizer, TradeExecutor, TradeLogger
from trader.position_sizer import kelly_position_size

# 환경변수에서 설정 로드
config = get_config()
configure_dependencies(config)

# 전역 에러 핸들러 설정
error_handler = get_global_error_handler()

# 로깅 설정
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s",
                    handlers=[logging.FileHandler(config.log_file), logging.StreamHandler()])


class ImprovedLiveTrader:
    """
    개선된 라이브 트레이더 클래스

    주요 개선사항:
    - 의존성 주입을 통한 설정 관리
    - 통일된 에러 처리
    - 모듈화된 컴포넌트들
    """

    def __init__(self):
        """초기화 및 의존성 설정"""
        self._running = True
        self.config = get_config()

        # 에러 핸들러 설정
        self.error_handler = ErrorHandler(Notifier(
            self.config.telegram_bot_token,
            self.config.telegram_chat_id
        ))

        # 핵심 컴포넌트들 초기화
        self._setup_components()

        # 전략 및 포지션 초기화
        self.strategies = {
            symbol: self._create_strategy(symbol) for symbol in self.config.symbols
        }
        self.positions: Dict[str, PositionStateManager] = self._load_positions()

        self.logger.info(f"Improved LiveTrader initialized with {len(self.strategies)} strategies")

    def _setup_components(self):
        """컴포넌트들 설정"""
        try:
            # Binance 클라이언트 설정
            self.client = Client(self.config.api_key, self.config.api_secret)

            # 데이터 제공자 설정
            self.data_provider = ImprovedBinanceData(
                api_key=self.config.api_key,
                secret_key=self.config.api_secret,
                error_handler=self.error_handler
            )

            # 상태 관리자 설정
            self.state_manager = StateManager("live_positions.json")

            # 트레이더 컴포넌트들 설정
            self.notifier = Notifier(
                self.config.telegram_bot_token,
                self.config.telegram_chat_id
            )

            self.position_sizer = PositionSizer(
                risk_per_trade=self.config.risk_per_trade,
                max_symbol_weight=self.config.max_symbol_weight,
                min_order_usdt=self.config.min_order_usdt,
            )

            # 트레이드 로거 설정
            live_log_dir = self.config.live_log_dir
            run_id = self.config.run_id or time.strftime("%Y%m%d_%H%M%S_" + self.config.strategy_name)
            self.trade_logger = TradeLogger(
                base_dir=live_log_dir,
                run_id=run_id,
                mode=self.config.order_execution,
                date_partition=("daily" if self.config.live_log_date_partition else "none"),
                tz=self.config.log_tz,
                date_fmt=self.config.log_date_fmt,
            )

            # 트레이드 실행자 설정
            self.executor = TradeExecutor(
                self.client,
                self.data_provider,
                self.state_manager,
                self.notifier,
                trade_logger=self.trade_logger,
            )

            # 실행 설정 적용
            self.executor.execution_mode = self.config.order_execution
            self.executor.max_slippage_bps = self.config.max_slippage_bps
            self.executor.order_timeout_sec = self.config.order_timeout_sec
            self.executor.order_retry = self.config.order_retry
            self.executor.kill_switch = self.config.kill_switch

            self.logger = logging.getLogger(__name__)

        except Exception as e:
            raise ConfigurationError(f"Failed to setup components: {e}") from e

    def _create_strategy(self, symbol: str) -> 'Strategy':
        """심볼별 전략 생성"""
        try:
            factory = StrategyFactory()
            strategy_config = self.config.get_strategy_config(symbol)

            return factory.create_strategy(
                strategy_name=self.config.strategy_name,
                symbol=symbol,
                config=strategy_config
            )
        except Exception as e:
            raise ConfigurationError(f"Failed to create strategy for {symbol}: {e}") from e

    def _load_positions(self) -> Dict[str, PositionStateManager]:
        """저장된 포지션들을 로드"""
        try:
            saved_positions = self.state_manager.load_positions()
            positions = {}

            for symbol, pos_dict in saved_positions.items():
                if symbol in self.config.symbols:
                    # 기존 Position 객체를 PositionStateManager로 변환
                    manager = PositionStateManager.from_dict(pos_dict, symbol)
                    positions[symbol] = manager

            self.logger.info(f"Loaded {len(positions)} positions from state file")
            return positions

        except Exception as e:
            self.error_handler.handle_error(
                e,
                context={"operation": "load_positions"},
                notify=True
            )
            return {}

    def run(self):
        """메인 트레이딩 루프"""
        self._notify_start()

        while self._running:
            try:
                with self.error_handler.create_safe_wrapper(log_level="warning")():
                    self._check_stops()
                    self._find_and_execute_entries()
                    time.sleep(self.config.execution_interval)

            except KeyboardInterrupt:
                self.logger.info("Received keyboard interrupt, shutting down...")
                break
            except Exception as e:
                self.error_handler.handle_error(
                    e,
                    context={"operation": "main_loop"},
                    notify=True
                )
                time.sleep(5)  # 에러 발생 시 잠시 대기

        self._shutdown()

    def _check_stops(self):
        """스탑 로스 조건 확인 및 실행"""
        for symbol, position in list(self.positions.items()):
            try:
                if position.status != "ACTIVE":
                    continue

                current_price = self.data_provider.get_current_price(symbol)
                if current_price <= 0:
                    continue

                if current_price <= position.trailing_stop_price:
                    self.logger.info(f"Stop triggered for {symbol}: {current_price} <= {position.trailing_stop_price}")
                    self._place_sell_order(symbol, position)

            except Exception as e:
                self.error_handler.handle_error(
                    e,
                    context={"symbol": symbol, "operation": "check_stops"},
                    notify=False  # 빈번한 에러는 알림하지 않음
                )

    def _find_and_execute_entries(self):
        """진입 신호 탐색 및 실행"""
        usdt_balance = self.executor.get_usdt_balance()

        if usdt_balance <= self.config.min_order_usdt:
            self.logger.info("Insufficient balance, skipping entries")
            return

        concurrent_positions = len([p for p in self.positions.values() if p.status == "ACTIVE"])

        for symbol in self.config.symbols:
            if symbol in self.positions or concurrent_positions >= self.config.max_concurrent_positions:
                continue

            try:
                strategy = self.strategies[symbol]
                market_data = self.data_provider.get_and_update_klines(symbol, self.config.execution_timeframe)
                current_position = self.positions.get(symbol)

                signal = strategy.get_signal(market_data, current_position)

                if signal == Signal.BUY:
                    self._execute_buy_order(symbol, usdt_balance, market_data)
                    concurrent_positions += 1

                elif signal == Signal.SELL:
                    self._place_sell_order(symbol)

            except Exception as e:
                self.error_handler.handle_error(
                    e,
                    context={"symbol": symbol, "operation": "find_entries"},
                    notify=False
                )

    def _execute_buy_order(self, symbol: str, usdt_balance: float, market_data: pd.DataFrame):
        """매수 주문 실행"""
        try:
            spend_amount = self._calculate_position_size(symbol, usdt_balance, market_data)

            if not spend_amount or spend_amount < self.config.min_order_usdt:
                return

            # 스코어 메타 정보 수집
            score_meta = self._get_score_metadata(symbol, market_data)

            self.logger.info(f"Executing BUY for {symbol}: {spend_amount}")

            # 개선된 PositionStateManager 생성
            position_manager = PositionService().create_position(
                symbol=symbol,
                quantity=0,  # 실제 수량은 주문 실행 후 설정
                entry_price=0,  # 실제 가격은 주문 실행 후 설정
                stop_price=0   # 실제 스탑 가격은 주문 실행 후 설정
            )

            self.positions[symbol] = position_manager

            # 주문 실행 (실제 주문 로직은 executor에 위임)
            self.executor.market_buy(
                symbol=symbol,
                usdt_to_spend=spend_amount,
                positions=self.positions,
                atr_multiplier=self.config.atr_multiplier,
                timeframe=self.config.execution_timeframe,
                k_sl=self.config.bracket_k_sl,
                rr=self.config.bracket_rr,
                score_meta=score_meta or {},
            )

        except Exception as e:
            self.error_handler.handle_error(
                e,
                context={"symbol": symbol, "operation": "execute_buy"},
                notify=True
            )

    def _calculate_position_size(self, symbol: str, usdt_balance: float, market_data: pd.DataFrame) -> Optional[float]:
        """포지션 크기 계산"""
        try:
            strategy = self.strategies.get(symbol)
            if not strategy:
                return None

            if self.config.strategy_name == "composite_signal" and hasattr(strategy, 'score'):
                # Kelly 기반 포지션 사이징
                score = float(getattr(strategy, "score", lambda x: 0.0)(market_data))
                max_score = float(getattr(getattr(strategy, "cfg", None), "max_score", 1.0))

                win_rate = 0.5
                avg_win = 1.0
                avg_loss = 1.0
                f_max = float(os.getenv("KELLY_FMAX", "0.2"))

                return kelly_position_size(
                    capital=usdt_balance,
                    win_rate=win_rate,
                    avg_win=avg_win,
                    avg_loss=avg_loss,
                    score=score,
                    max_score=max_score,
                    f_max=f_max,
                    pos_min=0.0,
                    pos_max=self.config.max_symbol_weight,
                )
            else:
                # 기존 방식
                return self.position_sizer.compute_spend_amount(usdt_balance, market_data)

        except Exception as e:
            self.error_handler.handle_error(
                e,
                context={"symbol": symbol, "operation": "calculate_position_size"},
                notify=False
            )
            return None

    def _get_score_metadata(self, symbol: str, market_data: pd.DataFrame) -> Optional[Dict]:
        """스코어 메타 정보 수집"""
        try:
            strategy = self.strategies.get(symbol)
            if not strategy or not hasattr(strategy, 'score'):
                return None

            score = float(strategy.score(market_data))
            max_score = float(getattr(getattr(strategy, "cfg", None), "max_score", 1.0))
            confidence = max(0.0, min(1.0, abs(score) / max(1e-9, max_score)))

            return {
                "score": score,
                "max_score": max_score,
                "confidence": confidence
            }

        except Exception:
            return None

    def _place_sell_order(self, symbol: str, position: Optional[PositionStateManager] = None):
        """매도 주문 실행"""
        try:
            self.executor.market_sell(symbol, self.positions)
        except Exception as e:
            self.error_handler.handle_error(
                e,
                context={"symbol": symbol, "operation": "place_sell_order"},
                notify=True
            )

    def _notify_start(self):
        """트레이더 시작 알림"""
        try:
            message = f"🚀 Improved Trader started in {self.config.mode} mode\n"
            message += f"Symbols: {', '.join(self.config.symbols)}\n"
            message += f"Strategy: {self.config.strategy_name}"

            self.notifier.send(message)
            self.trade_logger.log_event("Improved Trader started")
        except Exception as e:
            self.error_handler.handle_error(e, context={"operation": "notify_start"})

    def stop(self):
        """트레이더 중지"""
        self._running = False

    def _shutdown(self):
        """정리 작업"""
        self.logger.info("Shutting down Improved LiveTrader...")

        try:
            # 모든 포지션 정리
            for symbol in list(self.positions.keys()):
                self._place_sell_order(symbol)

            # 최종 성과 계산
            self._calculate_final_performance()

            # 종료 알림
            self.notifier.send("🛑 Improved Trader stopped")
            self.trade_logger.log_event("Improved Trader stopped")

        except Exception as e:
            self.error_handler.handle_error(e, context={"operation": "shutdown"})

    def _calculate_final_performance(self):
        """최종 성과 계산"""
        try:
            from trader.performance_calculator import PerformanceCalculator

            calculator = PerformanceCalculator(
                log_dir=self.trade_logger.base_dir,
                mode=self.config.mode
            )

            # 현재 활성 포지션들을 딕셔너리로 변환
            current_positions = {
                symbol: pos.to_dict()
                for symbol, pos in self.positions.items()
                if pos.status == "ACTIVE"
            }

            current_equity = self.config.min_order_usdt  # 기본값
            if self.config.mode == "REAL":
                current_equity = self.executor.get_usdt_balance()

            final_performance = calculator.calculate_performance(
                current_positions=current_positions,
                current_equity=current_equity
            )

            self.trade_logger.save_final_performance(final_performance)

            # 성과 알림
            total_return = final_performance.get('total_return_pct', 0.0)
            total_trades = final_performance.get('total_trades', 0)
            win_rate = final_performance.get('win_rate', 0.0)

            message = "📊 FINAL PERFORMANCE REPORT\n"
            message += f"Total Return: {total_return:.2f}%\n"
            message += f"Total Trades: {total_trades}\n"
            message += f"Win Rate: {win_rate:.1f}%"

            self.notifier.send(message)

        except Exception as e:
            self.error_handler.handle_error(e, context={"operation": "calculate_final_performance"})


# ------------------ Main Execution ------------------
_trader_instance = None

def shutdown_handler(signum, frame):
    """시그널 핸들러"""
    global _trader_instance
    logging.warning("Termination signal received. Shutting down...")
    if _trader_instance:
        _trader_instance.stop()

if __name__ == "__main__":
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    try:
        _trader_instance = ImprovedLiveTrader()
        _trader_instance.run()
    except Exception as e:
        logging.exception("A fatal error occurred in the improved trader.")
        if config.telegram_bot_token:
            requests.post(
                f"https://api.telegram.org/bot{config.telegram_bot_token}/sendMessage",
                json={"chat_id": config.telegram_chat_id, "text": f"🔥 FATAL ERROR: {e}"}
            )
        raise
