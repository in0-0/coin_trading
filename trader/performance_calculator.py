import logging
import os
from datetime import UTC, datetime
from typing import Any

import numpy as np
import pandas as pd

from models import Position


class PerformanceCalculator:
    """
    전체 트레이딩 성과를 계산하는 클래스

    trades.csv 파일과 현재 포지션 정보를 기반으로
    전체 수익률, 승률, 최대 낙폭 등을 계산합니다.
    """

    def __init__(self, log_dir: str, mode: str = "SIMULATED"):
        self.log_dir = log_dir
        self.mode = mode.upper()
        self.logger = logging.getLogger(__name__)

    def calculate_performance(self, current_positions: dict[str, Position],
                            current_equity: float = 1000.0) -> dict[str, Any]:
        """
        전체 트레이딩 성과를 계산합니다.

        Args:
            current_positions: 현재 열려있는 포지션들
            current_equity: 현재 자산 잔고 (USDT)

        Returns:
            성과 지표들을 담은 딕셔너리
        """
        try:
            # 1. 실현 손익 분석
            realized_metrics = self._calculate_realized_performance()

            # 2. 미실현 손익 계산
            unrealized_pnl = self._calculate_unrealized_pnl(current_positions)

            # 3. 전체 성과 계산
            total_pnl = realized_metrics.get('total_pnl', 0.0) + unrealized_pnl
            final_equity = current_equity + total_pnl

            # 4. 종합 성과 지표
            performance = {
                'timestamp': datetime.now(UTC).isoformat(),
                'mode': self.mode,
                'final_equity': final_equity,
                'initial_equity': current_equity,
                'total_return_pct': (final_equity / current_equity - 1.0) * 100 if current_equity > 0 else 0.0,

                # 실현 손익 관련
                'realized_pnl': realized_metrics.get('total_pnl', 0.0),
                'realized_pnl_pct': (realized_metrics.get('total_pnl', 0.0) / current_equity) * 100 if current_equity > 0 else 0.0,

                # 미실현 손익 관련
                'unrealized_pnl': unrealized_pnl,
                'unrealized_pnl_pct': (unrealized_pnl / current_equity) * 100 if current_equity > 0 else 0.0,

                # 거래 통계
                'total_trades': realized_metrics.get('total_trades', 0),
                'winning_trades': realized_metrics.get('winning_trades', 0),
                'losing_trades': realized_metrics.get('losing_trades', 0),
                'win_rate': realized_metrics.get('win_rate', 0.0),
                'avg_win': realized_metrics.get('avg_win', 0.0),
                'avg_loss': realized_metrics.get('avg_loss', 0.0),
                'profit_factor': realized_metrics.get('profit_factor', 0.0),
                'largest_win': realized_metrics.get('largest_win', 0.0),
                'largest_loss': realized_metrics.get('largest_loss', 0.0),

                # 위험 지표 (간단 버전)
                'max_drawdown_pct': self._calculate_max_drawdown(current_equity, final_equity),
                'sharpe_ratio': self._calculate_sharpe_ratio(realized_metrics),

                # 현재 포지션 정보
                'open_positions_count': len(current_positions),
                'open_positions_symbols': list(current_positions.keys()),

                # 파일 경로
                'log_directory': self.log_dir,
            }

            return performance

        except Exception as e:
            self.logger.error(f"Error calculating performance: {e}")
            return {
                'timestamp': datetime.now(UTC).isoformat(),
                'mode': self.mode,
                'error': str(e),
                'final_equity': current_equity,
                'total_return_pct': 0.0,
            }

    def _calculate_realized_performance(self) -> dict[str, Any]:
        """trades.csv 파일에서 실현 손익을 분석합니다."""
        trades_file = os.path.join(self.log_dir, "trades.csv")

        if not os.path.exists(trades_file):
            return {
                'total_pnl': 0.0,
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0.0,
                'avg_win': 0.0,
                'avg_loss': 0.0,
                'profit_factor': 0.0,
                'largest_win': 0.0,
                'largest_loss': 0.0,
            }

        try:
            df = pd.read_csv(trades_file)

            if df.empty:
                return self._get_empty_performance()

            # PnL 계산
            total_pnl = df['pnl'].sum()
            total_trades = len(df)

            if total_trades == 0:
                return self._get_empty_performance()

            # 승/패 거래 분리
            winning_trades = df[df['pnl'] > 0]
            losing_trades = df[df['pnl'] < 0]

            winning_count = len(winning_trades)
            losing_count = len(losing_trades)

            # 기본 지표들
            win_rate = (winning_count / total_trades) * 100 if total_trades > 0 else 0.0
            avg_win = winning_trades['pnl'].mean() if winning_count > 0 else 0.0
            avg_loss = abs(losing_trades['pnl'].mean()) if losing_count > 0 else 0.0
            largest_win = winning_trades['pnl'].max() if winning_count > 0 else 0.0
            largest_loss = abs(losing_trades['pnl'].min()) if losing_count > 0 else 0.0

            # Profit Factor (총이익 / 총손실)
            total_gains = winning_trades['pnl'].sum() if winning_count > 0 else 0.0
            total_losses = abs(losing_trades['pnl'].sum()) if losing_count > 0 else 0.0
            profit_factor = total_gains / total_losses if total_losses > 0 else float('inf')

            return {
                'total_pnl': total_pnl,
                'total_trades': total_trades,
                'winning_trades': winning_count,
                'losing_trades': losing_count,
                'win_rate': win_rate,
                'avg_win': avg_win,
                'avg_loss': avg_loss,
                'profit_factor': profit_factor,
                'largest_win': largest_win,
                'largest_loss': largest_loss,
            }

        except Exception as e:
            self.logger.error(f"Error reading trades.csv: {e}")
            return self._get_empty_performance()

    def _calculate_unrealized_pnl(self, positions: dict[str, Position]) -> float:
        """현재 포지션들의 미실현 손익을 계산합니다."""
        # 실제 구현 시에는 현재가를 조회해야 하지만,
        # 현재 시스템에서는 간단한 방법으로 계산
        total_unrealized = 0.0

        for symbol, position in positions.items():
            if position.is_open():
                # 현재가를 알 수 없으므로 0으로 처리
                # 실제 구현 시에는 data_provider.get_current_price(symbol) 사용
                unrealized = 0.0
                total_unrealized += unrealized

        return total_unrealized

    def _calculate_max_drawdown(self, initial_equity: float, final_equity: float) -> float:
        """최대 낙폭을 계산합니다 (간단 버전)."""
        if initial_equity <= 0:
            return 0.0

        # 실제로는 equity.csv나 더 자세한 자산 추적 데이터가 필요
        # 현재는 간단한 계산으로 대체
        current_drawdown = (initial_equity - final_equity) / initial_equity * 100
        return max(0.0, current_drawdown)

    def _calculate_sharpe_ratio(self, realized_metrics: dict[str, Any]) -> float:
        """샤프 비율을 계산합니다 (간단 버전)."""
        # 실제로는 일일 수익률의 변동성과 평균 수익률이 필요
        # 현재는 간단한 계산으로 대체
        total_trades = realized_metrics.get('total_trades', 0)
        if total_trades == 0:
            return 0.0

        avg_pnl = realized_metrics.get('total_pnl', 0.0) / total_trades

        # PnL의 표준편차를 간단하게 계산
        # 실제로는 더 정확한 변동성 계산 필요
        if total_trades > 1:
            # trades.csv의 모든 PnL 값들을 사용한 표준편차 계산
            trades_file = os.path.join(self.log_dir, "trades.csv")
            if os.path.exists(trades_file):
                try:
                    df = pd.read_csv(trades_file)
                    if not df.empty:
                        pnl_std = df['pnl'].std()
                        # 연율화된 샤프 비율 (일일 거래를 가정)
                        sharpe = (avg_pnl / pnl_std) * np.sqrt(252) if pnl_std > 0 else 0.0
                        return sharpe
                except Exception:
                    pass

        return 0.0

    def _get_empty_performance(self) -> dict[str, Any]:
        """빈 성과 데이터를 반환합니다."""
        return {
            'total_pnl': 0.0,
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'win_rate': 0.0,
            'avg_win': 0.0,
            'avg_loss': 0.0,
            'profit_factor': 0.0,
            'largest_win': 0.0,
            'largest_loss': 0.0,
        }
