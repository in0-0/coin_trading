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


class TestPhase2StrategyActions:
    """Phase 2: 전략의 get_position_action 메서드 테스트"""

    def test_composite_strategy_get_position_action(self):
        """Composite 전략의 get_position_action 메서드 테스트"""
        from strategies.composite_signal_strategy import CompositeSignalStrategy

        # Mock 설정 (모든 필요한 속성 포함)
        config = Mock()
        config.atr_len = 14
        config.buy_threshold = 0.3
        config.sell_threshold = -0.3
        config.max_score = 1.0
        config.ema_fast = 12
        config.ema_slow = 26
        config.bb_len = 20
        config.rsi_len = 14
        config.macd_fast = 12
        config.macd_slow = 26
        config.macd_signal = 9
        config.vol_len = 20
        config.obv_span = 20
        config.weights = Mock()
        config.weights.ma = 0.25
        config.weights.bb = 0.15
        config.weights.rsi = 0.15
        config.weights.macd = 0.25
        config.weights.vol = 0.1
        config.weights.obv = 0.1

        strategy = CompositeSignalStrategy(config)

        # 테스트 데이터 (Composite 스코어가 높도록 설정)
        # 강한 상승 신호를 위해 EMA 설정
        market_data = pd.DataFrame({
            'Open time': pd.date_range('2024-01-01', periods=30, freq='5min'),
            'Open': [50000.0 + i * 100 for i in range(30)],  # 상승 추세
            'High': [51000.0 + i * 100 for i in range(30)],
            'Low': [49000.0 + i * 100 for i in range(30)],
            'Close': [50500.0 + i * 100 for i in range(30)],  # 지속 상승
            'Volume': [100.0] * 30
        })

        # Mock 포지션 (불타기 조건 만족)
        position = Mock()
        position.legs = [Mock(price=50500.0)]  # 최근가가 높음
        position.qty = 1.0
        position.entry_price = 50000.0  # 진입가는 낮음
        position.trailing_stop_price = 49500.0

        # get_position_action 호출
        action = strategy.get_position_action(market_data, position)

        # 결과 검증
        assert action is not None
        assert hasattr(action, 'action_type')
        assert action.action_type in ["BUY_ADD", "UPDATE_TRAIL", "SELL_PARTIAL"]
        assert hasattr(action, 'metadata')
        assert 'reason' in action.metadata

    def test_atr_strategy_get_position_action(self):
        """ATR 전략의 get_position_action 메서드 테스트"""
        from strategies.atr_trailing_stop_strategy import ATRTrailingStopStrategy

        strategy = ATRTrailingStopStrategy('BTCUSDT', 0.5, 0.01)

        # 테스트 데이터
        market_data = pd.DataFrame({
            'Open time': [pd.Timestamp.now()],
            'Open': [50000.0],
            'High': [51000.0],
            'Low': [49000.0],
            'Close': [50500.0],
            'Volume': [100.0],
            'atr': [100.0]
        })

        # Mock 포지션
        position = Mock()
        position.legs = [Mock(price=50000.0)]
        position.qty = 1.0
        position.entry_price = 50000.0
        position.trailing_stop_price = 49500.0
        position.highest_price = 50000.0

        # get_position_action 호출
        action = strategy.get_position_action(market_data, position)

        # 결과 검증
        assert action is not None
        assert hasattr(action, 'action_type')
        assert action.action_type in ["BUY_ADD", "UPDATE_TRAIL", "SELL_PARTIAL"]
        assert hasattr(action, 'metadata')
        assert 'reason' in action.metadata

    def test_position_action_integration_in_trader(self):
        """트레이더에서 포지션 액션들이 제대로 처리되는지 테스트"""
        from models import PositionAction

        # Mock 액션 생성
        test_action = PositionAction(
            action_type="BUY_ADD",
            price=None,
            metadata={"pyramid_size": 100.0, "reason": "test_pyramid"}
        )

        # Mock 전략
        mock_strategy = Mock()
        mock_strategy.get_position_action = Mock(return_value=test_action)

        # Mock 포지션
        mock_position = Mock()
        mock_position.qty = 1.0
        mock_position.entry_price = 50000.0
        mock_position.trailing_stop_price = 49500.0

        # Mock 시장 데이터
        mock_market_data = pd.DataFrame({
            'Open time': [pd.Timestamp.now()],
            'Open': [50000.0],
            'High': [51000.0],
            'Low': [49000.0],
            'Close': [50500.0],
            'Volume': [100.0]
        })

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

            # Mock dependencies
            trader.strategies = {'BTCUSDT': mock_strategy}
            trader.positions = {'BTCUSDT': mock_position}

            # _find_and_execute_entries에서 포지션 액션이 처리되는지 확인
            source = inspect.getsource(trader._find_and_execute_entries)
            assert 'position_actions' in source
            assert 'get_position_action' in source
            assert '_handle_position_addition' in source
            assert '_handle_trailing_stop_update' in source
            assert '_handle_partial_exit' in source


class TestPhase3CompositeEnhancement:
    """Phase 3: Composite 전략 지원 강화 테스트"""

    def test_enhanced_kelly_position_sizing(self):
        """강화된 켈리 포지션 사이징 테스트"""
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

            # Mock Composite 전략 (score 메서드 포함)
            mock_strategy = Mock()
            mock_strategy.score = Mock(return_value=0.75)
            mock_strategy.cfg = Mock()
            mock_strategy.cfg.max_score = 1.0

            # 테스트 데이터
            market_data = pd.DataFrame({
                'Open time': pd.date_range('2024-01-01', periods=30, freq='5min'),
                'Open': [50000.0] * 30,
                'High': [51000.0] * 30,
                'Low': [49000.0] * 30,
                'Close': [50500.0] * 30,
                'Volume': [100.0] * 30
            })

            with patch.object(trader, 'strategies', {'BTCUSDT': mock_strategy}):
                position_size = trader._calculate_position_size('BTCUSDT', 1000.0, market_data)

                # 켈리 사이징이 제대로 작동하는지 확인
                assert position_size is not None
                assert position_size > 0
                assert position_size <= 1000.0 * 0.20  # max_symbol_weight 제한

    def test_composite_config_enhancement(self):
        """Composite 전략 설정 강화 테스트"""
        with patch('improved_live_trader.get_config') as mock_config, \
             patch('improved_live_trader.configure_dependencies'):

            # Mock TradingConfig에서 get_strategy_config 호출
            from core.dependency_injection import TradingConfig
            config = TradingConfig()
            config.strategy_name = "composite_signal"
            config.symbols = ["BTCUSDT"]
            config.execution_timeframe = "5m"
            config.atr_period = 14
            config.atr_multiplier = 0.5
            config.risk_per_trade = 0.005
            config.max_symbol_weight = 0.20

            strategy_config = config.get_strategy_config("BTCUSDT")

            # Composite 전략 설정이 강화되었는지 확인
            assert strategy_config.strategy_name == "composite_signal"
            assert hasattr(strategy_config, 'ema_fast')
            assert hasattr(strategy_config, 'ema_slow')
            assert hasattr(strategy_config, 'bb_len')
            assert hasattr(strategy_config, 'rsi_len')
            assert hasattr(strategy_config, 'weights')
            assert strategy_config.ema_fast == 12
            assert strategy_config.ema_slow == 26
            assert strategy_config.max_score == 1.0
            assert strategy_config.buy_threshold == 0.3

    def test_performance_calculation_and_save(self):
        """성과 계산 및 저장 테스트"""
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
                mode='SIMULATED'
            )

            trader = ImprovedLiveTrader()

            # Mock TradeLogger
            trader.trade_logger = Mock()
            trader.trade_logger.base_dir = "/tmp/test_logs"
            trader.trade_logger.save_final_performance = Mock()

            # Mock Notifier
            trader.notifier = Mock()

            # 성과 계산 메서드 호출
            trader._calculate_and_save_final_performance()

            # TradeLogger의 save_final_performance가 호출되었는지 확인
            trader.trade_logger.save_final_performance.assert_called_once()

            # Notifier의 send가 호출되었는지 확인
            trader.notifier.send.assert_called_once()
            assert "FINAL PERFORMANCE REPORT" in trader.notifier.send.call_args[0][0]


class TestPhase3Integration:
    """Phase 3 통합 테스트"""

    def test_full_composite_strategy_integration(self):
        """완전한 Composite 전략 통합 테스트"""
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
                mode='SIMULATED'
            )

            trader = ImprovedLiveTrader()

            # 모든 Phase 3 기능들이 제대로 구현되었는지 확인
            assert hasattr(trader, '_calculate_position_size')
            assert hasattr(trader, '_calculate_and_save_final_performance')
            assert hasattr(trader, '_get_enhanced_score_metadata')

            # Composite 전략 켈리 사이징이 작동하는지 확인
            mock_strategy = Mock()
            mock_strategy.score = Mock(return_value=0.6)
            mock_strategy.cfg = Mock()
            mock_strategy.cfg.max_score = 1.0

            market_data = pd.DataFrame({
                'Open time': pd.date_range('2024-01-01', periods=30, freq='5min'),
                'Open': [50000.0] * 30,
                'High': [51000.0] * 30,
                'Low': [49000.0] * 30,
                'Close': [50500.0] * 30,
                'Volume': [100.0] * 30
            })

            with patch.object(trader, 'strategies', {'BTCUSDT': mock_strategy}):
                position_size = trader._calculate_position_size('BTCUSDT', 1000.0, market_data)
                assert position_size is not None
                assert position_size > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
