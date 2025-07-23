#-*- coding: utf-8 -*-
import pandas as pd
import os

class Backtester:
    """전략의 성과를 측정하기 위한 백테스터 클래스"""

    def __init__(self, initial_capital=10000):
        self.initial_capital = initial_capital
        self.reset()

    def reset(self):
        """백테스터 상태를 초기화합니다."""
        self.cash = self.initial_capital
        self.position = 0
        self.portfolio_value = self.initial_capital
        self.trades = []
        self.portfolio_history = []
        # 성과 지표 초기화
        self.final_value = 0
        self.total_return = 0
        self.buy_and_hold_return = 0
        self.max_drawdown = 0

    def run(self, df: pd.DataFrame):
        """백테스팅을 실행하고 콘솔에 요약 결과를 출력합니다."""
        self.reset()

        for i, row in df.iterrows():
            if row['Signal'] == 1 and self.position == 0:
                self.position = self.cash / row['Close']
                self.cash = 0
                self.trades.append({'type': 'BUY', 'price': row['Close'], 'date': row['Open time']})

            elif row['Signal'] == -1 and self.position > 0:
                self.cash = self.position * row['Close']
                self.position = 0
                self.trades.append({'type': 'SELL', 'price': row['Close'], 'date': row['Open time']})
            
            current_value = self.cash + self.position * row['Close']
            self.portfolio_history.append(current_value)

        self._calculate_performance(df)
        self._print_summary()

    def _calculate_performance(self, df: pd.DataFrame):
        """성과 지표를 계산하여 인스턴스 변수에 저장합니다."""
        self.final_value = self.portfolio_history[-1]
        self.total_return = (self.final_value / self.initial_capital - 1) * 100
        self.buy_and_hold_return = (df['Close'].iloc[-1] / df['Close'].iloc[0] - 1) * 100

        portfolio_df = pd.DataFrame(self.portfolio_history, columns=['value'])
        peak = portfolio_df['value'].cummax()
        drawdown = (portfolio_df['value'] - peak) / peak
        self.max_drawdown = drawdown.min() * 100

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
        report.append(f"Interval: {interval}")
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
                report.append(f"- {trade['date']} | {trade['type']:<4} | Price: {trade['price']:>10.4f}")
        
        report.append("\n====== End of Report ======")
        return "\n".join(report)