import os
import tempfile
import unittest

from models import Position
from trader.performance_calculator import PerformanceCalculator


class TestPerformanceCalculator(unittest.TestCase):

    def setUp(self):
        """테스트 설정"""
        self.temp_dir = tempfile.mkdtemp()
        self.calculator = PerformanceCalculator(self.temp_dir, "SIMULATED")

    def tearDown(self):
        """테스트 정리"""
        # 임시 디렉토리 삭제는 생략 (테스트 확인용)

    def test_calculate_performance_empty_trades(self):
        """거래 기록이 없는 경우의 성과 계산 테스트"""
        performance = self.calculator.calculate_performance({}, 1000.0)

        self.assertEqual(performance['mode'], 'SIMULATED')
        self.assertEqual(performance['final_equity'], 1000.0)
        self.assertEqual(performance['total_return_pct'], 0.0)
        self.assertEqual(performance['total_trades'], 0)
        self.assertEqual(performance['win_rate'], 0.0)
        self.assertEqual(performance['open_positions_count'], 0)

    def test_calculate_performance_with_trades(self):
        """거래 기록이 있는 경우의 성과 계산 테스트"""
        # 테스트용 trades.csv 파일 생성
        trades_data = [
            {'ts': 1000, 'mode': 'SIMULATED', 'symbol': 'BTCUSDT', 'entry_price': 100.0, 'exit_price': 110.0, 'qty': 1.0, 'pnl': 10.0, 'pnl_pct': 10.0},
            {'ts': 2000, 'mode': 'SIMULATED', 'symbol': 'ETHUSDT', 'entry_price': 50.0, 'exit_price': 45.0, 'qty': 2.0, 'pnl': -10.0, 'pnl_pct': -10.0},
            {'ts': 3000, 'mode': 'SIMULATED', 'symbol': 'BTCUSDT', 'entry_price': 110.0, 'exit_price': 121.0, 'qty': 1.0, 'pnl': 11.0, 'pnl_pct': 10.0},
        ]

        trades_file = os.path.join(self.temp_dir, "trades.csv")
        with open(trades_file, 'w') as f:
            f.write("ts,mode,symbol,entry_price,exit_price,qty,pnl,pnl_pct\n")
            for trade in trades_data:
                f.write(f"{trade['ts']},{trade['mode']},{trade['symbol']},{trade['entry_price']},{trade['exit_price']},{trade['qty']},{trade['pnl']},{trade['pnl_pct']}\n")

        performance = self.calculator.calculate_performance({}, 1000.0)

        self.assertEqual(performance['total_trades'], 3)
        self.assertEqual(performance['winning_trades'], 2)
        self.assertEqual(performance['losing_trades'], 1)
        self.assertEqual(performance['win_rate'], 66.66666666666666)  # 2/3 * 100
        self.assertEqual(performance['realized_pnl'], 11.0)  # 10 + (-10) + 11
        self.assertEqual(performance['final_equity'], 1011.0)  # 1000 + 11
        self.assertAlmostEqual(performance['total_return_pct'], 1.1)  # 11/1000 * 100

    def test_calculate_performance_with_positions(self):
        """포지션이 있는 경우의 성과 계산 테스트"""
        # 현재 포지션 생성 (실제로는 현재가가 필요하지만 테스트에서는 단순화)
        position = Position("BTCUSDT", qty=1.0, entry_price=100.0)
        positions = {"BTCUSDT": position}

        performance = self.calculator.calculate_performance(positions, 1000.0)

        self.assertEqual(performance['open_positions_count'], 1)
        self.assertIn('BTCUSDT', performance['open_positions_symbols'])

    def test_calculate_performance_error_handling(self):
        """오류 발생 시의 처리 테스트"""
        # 잘못된 trades.csv 파일 생성
        trades_file = os.path.join(self.temp_dir, "trades.csv")
        with open(trades_file, 'w') as f:
            f.write("invalid,csv,content,with,wrong,format\n")

        performance = self.calculator.calculate_performance({}, 1000.0)

        # 오류가 발생하면 빈 결과가 반환되어야 함
        self.assertEqual(performance['realized_pnl'], 0.0)
        self.assertEqual(performance['total_trades'], 0)
        self.assertEqual(performance['win_rate'], 0.0)

    def test_calculate_realized_performance_comprehensive(self):
        """실현 손익 분석의 포괄적 테스트"""
        # 다양한 시나리오의 거래 데이터
        trades_data = [
            {'pnl': 100.0},  # 이익
            {'pnl': 50.0},   # 이익
            {'pnl': -30.0},  # 손실
            {'pnl': -20.0},  # 손실
            {'pnl': 200.0},  # 큰 이익
            {'pnl': -100.0}, # 큰 손실
        ]

        trades_file = os.path.join(self.temp_dir, "trades.csv")
        with open(trades_file, 'w') as f:
            f.write("ts,mode,symbol,entry_price,exit_price,qty,pnl,pnl_pct\n")
            for i, trade in enumerate(trades_data):
                f.write(f"{i*1000},SIMULATED,BTCUSDT,100.0,110.0,1.0,{trade['pnl']},10.0\n")

        performance = self.calculator.calculate_performance({}, 1000.0)

        expected_total_pnl = 100 + 50 - 30 - 20 + 200 - 100  # 200
        expected_win_rate = (3/6) * 100  # 50.0
        expected_avg_win = (100 + 50 + 200) / 3  # 116.666...
        expected_avg_loss = (30 + 20 + 100) / 3  # 50.0
        expected_profit_factor = (100 + 50 + 200) / (30 + 20 + 100)  # 350/150 = 2.333...

        self.assertEqual(performance['realized_pnl'], expected_total_pnl)
        self.assertEqual(performance['winning_trades'], 3)
        self.assertEqual(performance['losing_trades'], 3)
        self.assertAlmostEqual(performance['win_rate'], expected_win_rate)
        self.assertAlmostEqual(performance['avg_win'], expected_avg_win)
        self.assertAlmostEqual(performance['avg_loss'], expected_avg_loss)
        self.assertAlmostEqual(performance['profit_factor'], expected_profit_factor)
        self.assertEqual(performance['largest_win'], 200.0)
        self.assertEqual(performance['largest_loss'], 100.0)

    def test_calculate_sharpe_ratio(self):
        """샤프 비율 계산 테스트"""
        trades_data = [
            {'pnl': 10.0},
            {'pnl': 15.0},
            {'pnl': -5.0},
            {'pnl': 20.0},
            {'pnl': -10.0},
        ]

        trades_file = os.path.join(self.temp_dir, "trades.csv")
        with open(trades_file, 'w') as f:
            f.write("ts,mode,symbol,entry_price,exit_price,qty,pnl,pnl_pct\n")
            for i, trade in enumerate(trades_data):
                f.write(f"{i*1000},SIMULATED,BTCUSDT,100.0,110.0,1.0,{trade['pnl']},10.0\n")

        performance = self.calculator.calculate_performance({}, 1000.0)

        # 기본적으로 샤프 비율이 계산되어야 함
        sharpe_ratio = performance.get('sharpe_ratio', 0.0)
        self.assertIsInstance(sharpe_ratio, (int, float))

    def test_calculate_max_drawdown(self):
        """최대 낙폭 계산 테스트"""
        performance = self.calculator.calculate_performance({}, 1000.0)

        # 초기 자산이 최종 자산보다 크거나 같은 경우
        max_drawdown = performance.get('max_drawdown_pct', 0.0)
        self.assertIsInstance(max_drawdown, (int, float))
        self.assertGreaterEqual(max_drawdown, 0.0)

    def test_performance_with_zero_initial_equity(self):
        """초기 자산이 0인 경우 테스트"""
        performance = self.calculator.calculate_performance({}, 0.0)

        self.assertEqual(performance['total_return_pct'], 0.0)
        self.assertEqual(performance['final_equity'], 0.0)

    def test_performance_data_structure(self):
        """성과 데이터의 구조 검증"""
        performance = self.calculator.calculate_performance({}, 1000.0)

        # 필수 키들이 있는지 확인
        required_keys = [
            'timestamp', 'mode', 'final_equity', 'initial_equity', 'total_return_pct',
            'total_trades', 'winning_trades', 'losing_trades', 'win_rate',
            'open_positions_count', 'log_directory'
        ]

        for key in required_keys:
            self.assertIn(key, performance, f"Missing required key: {key}")

        # 타입 확인
        self.assertIsInstance(performance['timestamp'], str)
        self.assertIsInstance(performance['mode'], str)
        self.assertIsInstance(performance['final_equity'], (int, float))
        self.assertIsInstance(performance['total_trades'], int)
        self.assertIsInstance(performance['win_rate'], (int, float))


if __name__ == '__main__':
    unittest.main()
