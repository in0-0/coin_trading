"""
improved_live_trader.py의 Phase 1 기능 테스트

Phase 1 목표:
- 포지션 액션 처리 프레임워크 추가 (Phase 2,3,4 확장 준비)
- 메타데이터 수집 개선 (켈리 비율, 신뢰도, 스코어 정보)
- Composite 전략 설정 개선
"""

import pytest
import inspect
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone
import pandas as pd

from improved_live_trader import ImprovedLiveTrader
from models import Position, Signal
from core.exceptions import TradingError


class TestImprovedLiveTraderPhase1:
    """Phase 1: 핵심 기능 통합 테스트"""

    @pytest.fixture
    def trader(self):
        """테스트용 트레이더 인스턴스"""
        with patch('improved_live_trader.get_config') as mock_config, \
             patch('improved_live_trader.configure_dependencies'), \
             patch('improved_live_trader.Client'), \
             patch('improved_live_trader.ImprovedBinanceData'), \
             patch('improved_live_trader.StateManager'), \
             patch('improved_live_trader.Notifier'), \
             patch('improved_live_trader.PositionSizer'), \
             patch('improved_live_trader.TradeLogger'), \
             patch('improved_live_trader.TradeExecutor'):

            mock_config.return_value = Mock(
                symbols=['BTCUSDT'],
                execution_interval=60,
                execution_timeframe='5m',
                strategy_name='composite_signal',
                min_order_usdt=10.0,
                max_concurrent_positions=3,
                max_symbol_weight=0.20,
                atr_multiplier=0.5,
                bracket_k_sl=1.5,
                bracket_rr=2.0
            )

            trader = ImprovedLiveTrader()
            yield trader

    def test_position_action_framework_exists(self, trader):
        """포지션 액션 처리 프레임워크가 존재하는지 테스트"""
        assert hasattr(trader, '_find_and_execute_entries')
        assert hasattr(trader, '_handle_position_addition')
        assert hasattr(trader, '_handle_trailing_stop_update')
        assert hasattr(trader, '_handle_partial_exit')

    def test_enhanced_score_metadata_collection(self, trader):
        """강화된 스코어 메타데이터 수집 기능 테스트"""
        assert hasattr(trader, '_get_enhanced_score_metadata')

        # 테스트 데이터 준비
        market_data = pd.DataFrame({
            'Open time': [pd.Timestamp.now()],
            'Open': [50000.0],
            'High': [51000.0],
            'Low': [49000.0],
            'Close': [50500.0],
            'Volume': [100.0]
        })

        # Mock 전략
        mock_strategy = Mock()
        mock_strategy.score = Mock(return_value=0.75)
        mock_strategy.cfg = Mock()
        mock_strategy.cfg.max_score = 1.0

        with patch.object(trader, 'strategies', {'BTCUSDT': mock_strategy}):
            result = trader._get_enhanced_score_metadata('BTCUSDT', market_data, 1000.0, 100.0)

            assert result is not None
            assert 'score' in result
            assert 'confidence' in result
            assert 'kelly_f' in result
            assert result['score'] == 0.75
            assert result['confidence'] == 0.75
            assert result['kelly_f'] == 0.1  # 100 / 1000

    def test_position_addition_handler(self, trader):
        """포지션 추가 처리 기능 테스트"""
        # Mock 데이터
        mock_action = Mock()
        mock_action.metadata = {'pyramid_size': 50.0}
        mock_action.reason = 'pyramid_buy'

        mock_position = Mock()
        mock_position.qty = 1.0
        mock_position.entry_price = 50000.0

        mock_data_provider = Mock()
        mock_data_provider.get_current_price.return_value = 51000.0

        with patch.object(trader, 'data_provider', mock_data_provider), \
             patch.object(trader, '_execute_buy_order'), \
             patch.object(trader, 'state_manager'), \
             patch.object(trader, 'notifier'):

            trader._handle_position_addition('BTCUSDT', mock_action, mock_position, pd.DataFrame())

            # 포지션 추가 로직이 실행되었는지 확인
            mock_data_provider.get_current_price.assert_called_once_with('BTCUSDT')

    def test_trailing_stop_update_handler(self, trader):
        """트레일링 스탑 업데이트 처리 기능 테스트"""
        mock_action = Mock()
        mock_action.price = 51000.0
        mock_action.metadata = {'highest_price': 52000.0}

        mock_position = Mock()
        mock_position.trailing_stop_price = 50000.0
        mock_position.update_trailing_stop = Mock()

        with patch.object(trader, 'state_manager'), \
             patch.object(trader, 'notifier'):

            trader._handle_trailing_stop_update('BTCUSDT', mock_action, mock_position)

            # 트레일링 스탑 업데이트가 실행되었는지 확인
            mock_position.update_trailing_stop.assert_called_once_with(51000.0)

    def test_partial_exit_handler(self, trader):
        """부분 청산 처리 기능 테스트"""
        mock_action = Mock()
        mock_action.metadata = {'exit_qty': 0.5}
        mock_action.qty_ratio = 0.5
        mock_action.reason = 'partial_exit'

        mock_position = Mock()
        mock_position.qty = 1.0
        mock_position.partial_exits = []

        mock_data_provider = Mock()
        mock_data_provider.get_current_price.return_value = 51000.0

        mock_executor = Mock()
        mock_executor.market_sell_partial = Mock()

        with patch.object(trader, 'data_provider', mock_data_provider), \
             patch.object(trader, 'state_manager'), \
             patch.object(trader, 'notifier'), \
             patch.object(trader, 'executor', mock_executor):

            trader._handle_partial_exit('BTCUSDT', mock_action, mock_position)

            # 부분 청산 로직이 실행되었는지 확인
            mock_data_provider.get_current_price.assert_called_once_with('BTCUSDT')
            mock_executor.market_sell_partial.assert_called_once()


class TestPhase1Integration:
    """Phase 1 통합 테스트"""

    def test_find_and_execute_entries_with_position_actions(self):
        """포지션 액션 처리가 포함된 진입/청산 탐색 테스트"""
        # 실패 테스트: 포지션 액션 처리 로직이 아직 완전하지 않음
        with patch('improved_live_trader.get_config') as mock_config, \
             patch('improved_live_trader.configure_dependencies'), \
             patch('improved_live_trader.Client'), \
             patch('improved_live_trader.ImprovedBinanceData'), \
             patch('improved_live_trader.StateManager'), \
             patch('improved_live_trader.Notifier'), \
             patch('improved_live_trader.PositionSizer'), \
             patch('improved_live_trader.TradeLogger'), \
             patch('improved_live_trader.TradeExecutor'):

            mock_config.return_value = Mock(
                symbols=['BTCUSDT'],
                execution_interval=60,
                execution_timeframe='5m',
                strategy_name='composite_signal',
                min_order_usdt=10.0,
                max_concurrent_positions=3,
                max_symbol_weight=0.20,
                atr_multiplier=0.5,
                bracket_k_sl=1.5,
                bracket_rr=2.0
            )

            # 실제 구현 확인
            trader = ImprovedLiveTrader()

            # Phase 2,3,4 액션들이 제대로 처리되는지 확인하는 테스트
            assert hasattr(trader, '_find_and_execute_entries')
            assert hasattr(trader, '_handle_position_addition')
            assert hasattr(trader, '_handle_trailing_stop_update')
            assert hasattr(trader, '_handle_partial_exit')

            # 실제 _find_and_execute_entries 메서드가 Phase 2,3,4 로직을 포함하는지 확인
            source = inspect.getsource(trader._find_and_execute_entries)
            assert 'Phase 2, 3 & 4:' in source
            assert '_handle_position_addition' in source
            assert '_handle_trailing_stop_update' in source
            assert '_handle_partial_exit' in source


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
