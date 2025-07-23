#-*- coding: utf-8 -*-
import pandas as pd

class Backtester:
    """전략의 성과를 측정하기 위한 백테스터 클래스"""

    def __init__(self, initial_capital=10000, take_profit_pct=None, stop_loss_pct=None):
        self.initial_capital = initial_capital
        self.take_profit_pct = take_profit_pct
        self.stop_loss_pct = stop_loss_pct
        self.reset()

    def reset(self):
        """백테스터 상태를 초기화합니다."""
        self.cash = self.initial_capital
        self.position_size = 0
        self.entry_price = 0
        self.portfolio_value = self.initial_capital
        self.trades = []
        self.portfolio_history = []
        # 성과 지표 초기화
        self.final_value = 0
        self.total_return = 0
        self.buy_and_hold_return = 0
        self.max_drawdown = 0

    def run(self, df: pd.DataFrame):
        """백테스팅을 실행합니다."""
        self.reset()

        for i, row in df.iterrows():
            position_closed_in_frame = False
            # --- 청산 로직 ---
            if self.position_size > 0:
                # 익절 조건 확인
                if self.take_profit_pct and row['High'] >= self.entry_price * (1 + self.take_profit_pct):
                    sell_price = self.entry_price * (1 + self.take_profit_pct)
                    self._close_position(sell_price, row['Open time'], 'TAKE PROFIT')
                    position_closed_in_frame = True
                
                # 손절 조건 확인
                elif self.stop_loss_pct and row['Low'] <= self.entry_price * (1 - self.stop_loss_pct):
                    sell_price = self.entry_price * (1 - self.stop_loss_pct)
                    self._close_position(sell_price, row['Open time'], 'STOP LOSS')
                    position_closed_in_frame = True

                # 전략 자체의 매도 신호 확인 (e.g., ma_cross)
                elif row['Signal'] == -1:
                    self._close_position(row['Close'], row['Open time'], 'SELL SIGNAL')
                    position_closed_in_frame = True

            # --- 진입 로직 ---
            if not position_closed_in_frame and row['Signal'] == 1 and self.position_size == 0:
                self.position_size = self.cash / row['Close']
                self.entry_price = row['Close']
                self.cash = 0
                self.trades.append({'type': 'BUY', 'price': self.entry_price, 'date': row['Open time']})
            
            # 포트폴리오 가치 업데이트
            current_value = self.cash + self.position_size * row['Close']
            self.portfolio_history.append(current_value)

        # 데이터 기간 종료 시점에 포지션을 보유하고 있다면 시장가로 청산
        if self.position_size > 0:
            self._close_position(df['Close'].iloc[-1], df['Open time'].iloc[-1], 'END OF DATA')
            self.portfolio_history[-1] = self.cash

        self._calculate_performance(df)
        self._print_summary()

    def _close_position(self, price, date, trade_type):
        """포지션을 청산하고 거래를 기록합니다."""
        self.cash = self.position_size * price
        self.position_size = 0
        self.trades.append({'type': trade_type, 'price': price, 'date': date})
        self.entry_price = 0

    def _calculate_performance(self, df: pd.DataFrame):
        """성과 지표를 계산하여 인스턴스 변수에 저장합니다."""
        if not self.portfolio_history:
            self.final_value = self.initial_capital
        else:
            self.final_value = self.portfolio_history[-1]
        
        self.total_return = (self.final_value / self.initial_capital - 1) * 100
        
        if df.empty or df['Close'].iloc[0] == 0:
            self.buy_and_hold_return = 0
        else:
            self.buy_and_hold_return = (df['Close'].iloc[-1] / df['Close'].iloc[0] - 1) * 100

        if not self.portfolio_history:
            self.max_drawdown = 0
            return

        portfolio_df = pd.DataFrame(self.portfolio_history, columns=['value'])
        peak = portfolio_df['value'].cummax()
        drawdown = (portfolio_df['value'] - peak) / peak
        self.max_drawdown = 0 if drawdown.empty else drawdown.min() * 100

    def _print_summary(self):
        """계산된 성과를 콘솔에 출력합니다."""
        print("\n--- Backtesting Results ---")
        print(f"Initial Capital: ${self.initial_capital:,.2f}")
        print(f"Final Portfolio Value: ${self.final_value:,.2f}")
        print(f"Total Return: {self.total_return:.2f}%")
        print(f"Buy & Hold Return: {self.buy_and_hold_return:.2f}%")
        print(f"Max Drawdown (MDD): {self.max_drawdown:.2f}%")
        print(f"Number of Trades: {len(self.trades)}")

    def get_report_string(self, strategy_name, symbol, interval):
        """파일에 저장할 상세 리포트 문자열을 생성합니다."""
        report = []
        report.append("====== Backtest Report ======")
        report.append(f"Strategy: {strategy_name}")
        report.append(f"Symbol: {symbol}")
        report.append(f"Interval: {str(interval)}")
        report.append("-----------------------------")
        report.append("\n## Performance Summary ##")
        report.append(f"Initial Capital: ${self.initial_capital:,.2f}")
        report.append(f"Final Portfolio Value: ${self.final_value:,.2f}")
        report.append(f"Total Return: {self.total_return:.2f}%")
        report.append(f"Buy & Hold Return: {self.buy_and_hold_return:.2f}%")
        report.append(f"Max Drawdown (MDD): {self.max_drawdown:.2f}%")
        report.append(f"Number of Trades: {len(self.trades)}")
        report.append("\n## Trade Log ##")
        if not self.trades:
            report.append("No trades were made.")
        else:
            for trade in self.trades:
                report.append(f"- {trade['date']} | {trade['type']:<11} | Price: {trade['price']:>10.4f}")
        
        report.append("\n====== End of Report ======")
        return "\n".join(report)