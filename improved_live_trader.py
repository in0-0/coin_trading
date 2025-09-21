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
from typing import Dict, Optional, Callable, cast

import requests
import pandas as pd
from binance.client import Client

# --- Import Improved Modules ---
from core.error_handler import ErrorHandler, get_global_error_handler
from core.dependency_injection import get_config, configure_dependencies
from core.exceptions import TradingError, ConfigurationError, DataError
from core.data_models import StrategyConfig, MarketDataSummary
from binance_data_improved import ImprovedBinanceData
from improved_strategy_factory import StrategyFactory
from state_manager import StateManager
from models import Position, Signal
from trader import Notifier, PositionSizer, TradeExecutor, TradeLogger
from trader.position_sizer import kelly_position_size
from strategies.base_strategy import Strategy
from dotenv import load_dotenv
load_dotenv()
# 환경변수에서 설정 로드
config = get_config()
configure_dependencies(config)

# 전역 에러 핸들러 설정
error_handler = get_global_error_handler()

# 로깅 설정
logging.basicConfig(level=logging.DEBUG,
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
        self.positions: Dict[str, Position] = self._load_positions()

        self.logger.info(f"Improved LiveTrader initialized with {len(self.strategies)} strategies")

    def _setup_components(self):
        """컴포넌트들 설정"""
        try:
            # Binance 클라이언트 설정
            self.client = Client(self.config.api_key, self.config.api_secret, testnet=(self.config.mode == "TESTNET"))

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

    def _create_strategy(self, symbol: str) -> Strategy:
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

    def _load_positions(self) -> Dict[str, Position]:
        """저장된 포지션들을 로드"""
        try:
            saved_positions = self.state_manager.load_positions()  # dict[str, Position]
            positions: Dict[str, Position] = {}

            for symbol, pos in saved_positions.items():
                if symbol in self.config.symbols and isinstance(pos, Position):
                    positions[symbol] = pos

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
                with self.error_handler.create_safe_context(log_level="warning"):
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
        """진입 신호 탐색 및 실행 (Phase 2,3,4 지원)"""
        usdt_balance = self.executor.get_usdt_balance()

        if usdt_balance <= self.config.min_order_usdt:
            self.logger.info("Insufficient balance, skipping entries")
            return

        concurrent_positions = len([p for p in self.positions.values() if p.status == "ACTIVE"])
        self.logger.info(f"USDT Balance: {usdt_balance:.2f}, Active positions: {concurrent_positions}/{self.config.max_concurrent_positions}")

        for symbol in self.config.symbols:
            if symbol in self.positions or concurrent_positions >= self.config.max_concurrent_positions:
                continue

            try:
                strategy = self.strategies[symbol]
                market_data = self.data_provider.get_and_update_klines(symbol, self.config.execution_timeframe)
                current_position = self.positions.get(symbol)

                signal = strategy.get_signal(market_data, current_position)
                self.logger.info(f"Signal for {symbol}: {signal}")

                # Phase 1: 포지션 액션 처리 (향후 Phase 2, 3, 4에서 확장)
                position_actions = []
                if current_position and hasattr(strategy, 'get_position_action'):
                    try:
                        action = strategy.get_position_action(market_data, current_position)
                        if action:
                            position_actions.append(action)
                    except Exception as e:
                        self.logger.warning(f"Error getting position action for {symbol}: {e}")

                # Phase 2, 3 & 4: 포지션 액션 처리
                for action in position_actions:
                    if action.action_type == "BUY_ADD":
                        self._handle_position_addition(symbol, action, current_position, market_data)
                    elif action.action_type == "UPDATE_TRAIL":
                        self._handle_trailing_stop_update(symbol, action, current_position)
                    elif action.action_type == "SELL_PARTIAL":
                        self._handle_partial_exit(symbol, action, current_position)

                if signal == Signal.BUY:
                    self.logger.info(f"BUY signal detected for {symbol}, executing order")
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

    def _handle_position_addition(self, symbol: str, action: dict, position: Position, market_data: pd.DataFrame):
        """Phase 2: 불타기/물타기 포지션 추가 처리"""
        try:
            current_price = self.data_provider.get_current_price(symbol)
            if current_price <= 0:
                self.logger.warning(f"Cannot add position for {symbol}: invalid current price")
                return

            # 액션에서 사이즈 정보 추출
            spend_amount = action.metadata.get("pyramid_size") or action.metadata.get("averaging_size", 0)
            if not spend_amount:
                # 기본 계산 (현재 포지션의 50%)
                spend_amount = position.qty * position.entry_price * 0.5

            if spend_amount < self.config.min_order_usdt:
                self.logger.info(f"Skipping position addition for {symbol}: amount too small ({spend_amount})")
                return

            # 새로운 PositionLeg 생성
            from models import PositionLeg
            new_leg = PositionLeg(
                timestamp=datetime.now(timezone.utc),
                side="BUY",
                qty=spend_amount / current_price,
                price=current_price,
                reason=action.reason
            )

            # 포지션에 레그 추가
            position.add_leg(new_leg)

            # 실제 매수 주문 실행
            self.logger.info(f"Phase 2: Adding position for {symbol}, amount={spend_amount}, reason={action.reason}")
            self._execute_buy_order(symbol, spend_amount)

            # 포지션 저장
            self.state_manager.upsert_position(symbol, position)

            # 알림
            self.notifier.send(f"📈 {action.reason.upper()} {symbol}\n"
                              f"Added: {new_leg.qty:.6f} @ ${current_price:.4f}\n"
                              f"New avg: ${position.entry_price:.4f}")

        except Exception as e:
            self.error_handler.handle_error(
                e,
                context={"symbol": symbol, "operation": "handle_position_addition"},
                notify=True
            )

    def _handle_trailing_stop_update(self, symbol: str, action: dict, position: Position):
        """Phase 3: 트레일링 스탑 업데이트 처리"""
        try:
            new_trail_price = action.price
            if new_trail_price is None:
                self.logger.warning(f"Cannot update trailing stop for {symbol}: no price provided")
                return

            # 기존 트레일링 스탑과 비교
            old_trail = position.trailing_stop_price

            # 트레일링 스탑 업데이트
            position.update_trailing_stop(new_trail_price)

            # 포지션 저장
            self.state_manager.upsert_position(symbol, position)

            # 알림
            self.notifier.send(f"🔄 TRAILING STOP UPDATED {symbol}\n"
                              f"Old: ${old_trail:.4f} → New: ${new_trail_price:.4f}\n"
                              f"Highest: ${action.metadata.get('highest_price', 0):.4f}")

            self.logger.info(f"Phase 3: Trailing stop updated for {symbol}: {old_trail} -> {new_trail_price}")

        except Exception as e:
            self.error_handler.handle_error(
                e,
                context={"symbol": symbol, "operation": "handle_trailing_stop_update"},
                notify=True
            )

    def _handle_partial_exit(self, symbol: str, action: dict, position: Position):
        """Phase 4: 부분 청산 처리"""
        try:
            current_price = self.data_provider.get_current_price(symbol)
            if current_price <= 0:
                self.logger.warning(f"Cannot partial exit for {symbol}: invalid current price")
                return

            # 부분 청산 수량 계산
            exit_qty = action.metadata.get("exit_qty", 0)
            if exit_qty <= 0:
                exit_qty = position.qty * action.qty_ratio

            # 최소 주문 수량 확인
            if exit_qty < self.config.min_order_usdt / current_price:
                self.logger.info(f"Skipping partial exit for {symbol}: qty too small ({exit_qty})")
                return

            # 새로운 PositionLeg 생성 (청산)
            from models import PositionLeg
            exit_leg = PositionLeg(
                timestamp=datetime.now(timezone.utc),
                side="SELL",
                qty=exit_qty,
                price=current_price,
                reason=action.reason
            )

            # 부분 청산 이력 추가
            position.partial_exits.append(exit_leg)

            # 실제 매도 주문 실행
            self.logger.info(f"Phase 4: Partial exit for {symbol}, qty={exit_qty}, reason={action.reason}")
            self.executor.market_sell_partial(symbol, position, exit_qty, {"partial_exit": True, "reason": action.reason})

            # 포지션 저장
            self.state_manager.upsert_position(symbol, position)

            # 알림
            profit_pct = action.metadata.get("profit_pct", 0)
            unrealized_pct = action.metadata.get("unrealized_pct", 0)
            self.notifier.send(f"🟡 PARTIAL EXIT {symbol}\n"
                              f"Exited: {exit_leg.qty:.6f} @ ${current_price:.4f}\n"
                              f"Profit: {profit_pct:.1%} (Total: {unrealized_pct:.1%})")

        except Exception as e:
            self.error_handler.handle_error(
                e,
                context={"symbol": symbol, "operation": "handle_partial_exit"},
                notify=True
            )

    def _execute_buy_order(self, symbol: str, usdt_balance: float, market_data: pd.DataFrame):
        """매수 주문 실행 (메타데이터 수집 강화)"""
        try:
            spend_amount = self._calculate_position_size(symbol, usdt_balance, market_data)

            if not spend_amount or spend_amount < self.config.min_order_usdt:
                return

            # 스코어 메타 정보 수집 (개선된 버전)
            score_meta = self._get_enhanced_score_metadata(symbol, market_data, usdt_balance, spend_amount)

            self.logger.info(f"Executing BUY for {symbol}: {spend_amount}, meta: {score_meta}")

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

    def _get_enhanced_score_metadata(self, symbol: str, market_data: pd.DataFrame, usdt_balance: float, spend_amount: float) -> Optional[Dict]:
        """강화된 스코어 메타 정보 수집 (live_trader_gpt.py와 동일)"""
        try:
            strategy = self.strategies.get(symbol)
            if not strategy:
                return None

            score_fn_obj = getattr(strategy, 'score', None) if strategy else None
            if not callable(score_fn_obj):
                return None

            score_fn = cast(Callable[[pd.DataFrame], float], score_fn_obj)
            score = float(score_fn(market_data))
            max_score = float(getattr(getattr(strategy, "cfg", None), "max_score", 1.0))
            confidence = max(0.0, min(1.0, abs(score) / max(1e-9, max_score)))

            # 켈리 비율 계산 (live_trader_gpt.py와 동일)
            kelly_fraction = min(self.config.max_symbol_weight, max(0.0, spend_amount / max(1e-9, usdt_balance)))

            return {
                "score": score,
                "max_score": max_score,
                "confidence": confidence,
                "kelly_f": kelly_fraction,
                "position_size": spend_amount,
                "available_balance": usdt_balance
            }

        except Exception as e:
            self.logger.warning(f"Failed to collect enhanced score metadata for {symbol}: {e}")
            return None

    def _calculate_position_size(self, symbol: str, usdt_balance: float, market_data: pd.DataFrame) -> Optional[float]:
        """포지션 크기 계산 (live_trader_gpt.py와 동일한 로직)"""
        try:
            strategy = self.strategies.get(symbol)
            if not strategy:
                return None

            if self.config.strategy_name == "composite_signal" and hasattr(strategy, "score"):
                # Composite 전략: Kelly 기반 포지션 사이징 (live_trader_gpt.py와 동일)
                try:
                    s_raw = strategy.score(market_data)
                    s = float(s_raw) if isinstance(s_raw, (int, float)) else 0.0
                except Exception:
                    s = 0.0

                try:
                    max_score_val = getattr(getattr(strategy, "cfg", None), "max_score", 1.0) if hasattr(strategy, "cfg") else 1.0
                    max_score = float(max_score_val) if isinstance(max_score_val, (int, float)) else 1.0
                except Exception:
                    max_score = 1.0

                # Conservative defaults for Kelly inputs when live stats are unavailable
                win_rate = 0.5
                avg_win = 1.0
                avg_loss = 1.0
                f_max = float(os.getenv("KELLY_FMAX", "0.2"))

                pos = kelly_position_size(
                    capital=usdt_balance,
                    win_rate=win_rate,
                    avg_win=avg_win,
                    avg_loss=avg_loss,
                    score=s,
                    max_score=max_score,
                    f_max=f_max,
                    pos_min=0.0,
                    pos_max=self.config.max_symbol_weight,
                )
                return pos if pos >= self.config.min_order_usdt else None
            else:
                # ATR 등 다른 전략: 기존 방식 사용
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
            strategy = self.strategies.get(symbol)
            score_fn_obj = getattr(strategy, 'score', None) if strategy else None
            if not callable(score_fn_obj):
                return None

            score_fn = cast(Callable[[pd.DataFrame], float], score_fn_obj)
            score = float(score_fn(market_data))
            max_score = float(getattr(getattr(strategy, "cfg", None), "max_score", 1.0))
            confidence = max(0.0, min(1.0, abs(score) / max(1e-9, max_score)))

            return {
                "score": score,
                "max_score": max_score,
                "confidence": confidence
            }

        except Exception:
            return None

    def _place_sell_order(self, symbol: str, position: Optional[Position] = None):
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
        """정리 작업 (live_trader_gpt.py와 동일한 로직)"""
        self.logger.info("Shutting down Improved LiveTrader...")

        try:
            # 모든 포지션 정리
            for symbol in list(self.positions.keys()):
                self._place_sell_order(symbol)

            # 최종 성과 계산 및 기록
            self._calculate_and_save_final_performance()
            self.trade_logger.log_event("Final performance calculated and saved")

        except Exception as e:
            self.error_handler.handle_error(e, context={"operation": "shutdown"})
        finally:
            try:
                # 종료 알림
                self.notifier.send("🛑 Improved Trader stopped")
                self.trade_logger.log_event("Improved Trader stopped")
            except Exception:
                pass

    def _calculate_and_save_final_performance(self):
        """프로그램 종료 시점의 최종 성과를 계산하고 저장 (live_trader_gpt.py와 동일)"""
        try:
            # 현재 자산 잔고 조회 (시뮬레이션 모드에서는 초기값 사용)
            current_equity = self.config.min_order_usdt  # 기본값

            if self.config.mode == "REAL":
                try:
                    current_equity = self._get_account_balance_usdt()
                except Exception as e:
                    self.logger.warning(f"Could not get real account balance: {e}")
            else:
                # 시뮬레이션 모드: 최소 주문 금액을 기준으로 함
                # 실제로는 더 정확한 잔고 추적이 필요
                current_equity = self.config.min_order_usdt

            # PerformanceCalculator를 사용하여 성과 계산
            from trader.performance_calculator import PerformanceCalculator
            calculator = PerformanceCalculator(
                log_dir=self.trade_logger.base_dir,
                mode=self.config.mode
            )

            # 남은 포지션이 없으므로 빈 딕셔너리 전달
            final_performance = calculator.calculate_performance(
                current_positions={},
                current_equity=current_equity
            )

            # TradeLogger를 통해 저장
            self.trade_logger.save_final_performance(final_performance)

            # 텔레그램 알림
            total_return = final_performance.get('total_return_pct', 0.0)
            total_trades = final_performance.get('total_trades', 0)
            win_rate = final_performance.get('win_rate', 0.0)

            performance_msg = (
                "📊 FINAL PERFORMANCE REPORT\n"
                f"Total Return: {total_return:.2f}%\n"
                f"Total Trades: {total_trades}\n"
                f"Win Rate: {win_rate:.1f}%\n"
                f"Final Equity: ${final_performance.get('final_equity', current_equity):.2f}"
            )

            if total_trades > 0:
                profit_factor = final_performance.get('profit_factor', 0.0)
                sharpe_ratio = final_performance.get('sharpe_ratio', 0.0)
                performance_msg += f"\nProfit Factor: {profit_factor:.2f}"
                if sharpe_ratio > 0:
                    performance_msg += f"\nSharpe Ratio: {sharpe_ratio:.2f}"

            self.notifier.send(performance_msg)

            self.logger.info(f"Final performance calculated: {total_return:.2f}% return, "
                          f"{total_trades} trades, {win_rate:.1f}% win rate")

        except Exception as e:
            error_msg = f"❌ Error calculating final performance: {e}"
            self.notifier.send(error_msg)
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
