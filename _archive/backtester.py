import numpy as np
import pandas as pd
from position_sizer import PositionSizer


class Backtester:
    """전략의 성과를 측정하고 상세한 리포트를 생성하는 백테스터 클래스"""

    def __init__(self, initial_capital=10000, position_sizer: PositionSizer = None):
        self.initial_capital = initial_capital
        self.position_sizer = position_sizer
        self.reset()

    def reset(self):
        """백테스터의 모든 상태를 초기화합니다."""
        self.cash = self.initial_capital
        self.position_size = 0
        self.entry_price = 0
        self.entry_bar_index = None
        self.portfolio_value = self.initial_capital
        self.trades = []
        self.portfolio_history = []
        self.event_log = []

    def run(
        self,
        df: pd.DataFrame,
        take_profit_pct=None,
        stop_loss_pct=None,
        time_cut_period=None,
        reaches_ma=False,
    ):
        """
        백테스팅을 실행하고, 성과 리포트를 반환합니다.
        """
        self.reset()

        if "Open time" not in df.columns:
            raise ValueError("DataFrame에 'Open time' 컬럼이 없습니다.")

        df_reset = df.reset_index()
        ma_col = next((col for col in df.columns if col.startswith("MA_")), None)

        for i, row in df_reset.iterrows():
            position_closed_in_frame = False

            if self.position_size > 0:
                if take_profit_pct and row["High"] >= self.entry_price * (
                    1 + take_profit_pct
                ):
                    sell_price = self.entry_price * (1 + take_profit_pct)
                    self._close_position(sell_price, row["Open time"], "TAKE PROFIT")
                    position_closed_in_frame = True
                elif stop_loss_pct and row["Low"] <= self.entry_price * (
                    1 - stop_loss_pct
                ):
                    sell_price = self.entry_price * (1 - stop_loss_pct)
                    self._close_position(sell_price, row["Open time"], "STOP LOSS")
                    position_closed_in_frame = True
                elif (
                    time_cut_period
                    and self.entry_bar_index is not None
                    and (i - self.entry_bar_index) >= time_cut_period
                ):
                    self._close_position(row["Close"], row["Open time"], "TIME CUT")
                    position_closed_in_frame = True
                elif (
                    reaches_ma
                    and ma_col
                    and not pd.isna(row[ma_col])
                    and row["High"] >= row[ma_col]
                ):
                    self._close_position(row[ma_col], row["Open time"], "REACHES MA")
                    position_closed_in_frame = True
                elif row["Signal"] == -1:
                    self._close_position(row["Close"], row["Open time"], "SELL SIGNAL")
                    position_closed_in_frame = True

            if (
                not position_closed_in_frame
                and row["Signal"] == 1
                and self.position_size == 0
            ):
                self._open_position(row, i, stop_loss_pct)

            # 포트폴리오 히스토리 기록
            self._record_portfolio_history(row)

        if self.position_size > 0:
            self._close_position(
                df["Close"].iloc[-1], df["Open time"].iloc[-1], "END OF DATA"
            )
            if self.portfolio_history:
                self.portfolio_history[-1]["value"] = self.cash
                self.portfolio_history[-1]["cash"] = self.cash
                self.portfolio_history[-1]["position_value"] = 0

        return self.generate_report(df)

    def _open_position(self, row, index, stop_loss_pct):
        """포지션을 개시하고 거래를 기록합니다."""
        price = row["Close"]
        stop_loss_price = price * (1 - stop_loss_pct) if stop_loss_pct else None

        size = self.position_sizer.calculate_size(
            self.cash, price, stop_loss_price=stop_loss_price
        )
        if size <= 0:
            self.event_log.append(
                f"{row['Open time']}: BUY signal, but position size is 0. No trade executed."
            )
            return

        self.position_size = size
        self.entry_price = price
        self.entry_bar_index = index
        self.cash -= size * price
        self.trades.append(
            {
                "type": "BUY",
                "entry_date": row["Open time"],
                "entry_price": price,
                "exit_date": None,
                "exit_price": None,
                "profit_pct": None,
            }
        )

    def _close_position(self, price, date, trade_type):
        """포지션을 청산하고 거래 및 수익률을 기록합니다."""
        if self.position_size > 0:
            profit = (price / self.entry_price - 1) if self.entry_price > 0 else 0

            if self.trades and self.trades[-1]["exit_date"] is None:
                last_trade = self.trades[-1]
                last_trade.update(
                    {
                        "type": trade_type,
                        "exit_date": date,
                        "exit_price": price,
                        "profit_pct": profit * 100,
                    }
                )

            self.cash += self.position_size * price
            self.position_size = 0
            self.entry_price = 0
            self.entry_bar_index = None

    def _record_portfolio_history(self, row):
        """매 시점의 포트폴리오 상태를 기록합니다."""
        position_value = self.position_size * row["Close"]
        total_value = self.cash + position_value
        self.portfolio_history.append(
            {
                "date": row["Open time"],
                "total_value": total_value,
                "cash": self.cash,
                "position_size": self.position_size,
                "position_value": position_value,
            }
        )

    def generate_report(self, df: pd.DataFrame) -> dict:
        """성과 지표를 계산하고, 전체 리포트를 생성합니다."""
        portfolio_df = pd.DataFrame(self.portfolio_history)
        trades_df = pd.DataFrame(self.trades)

        initial_value = self.initial_capital
        final_value = (
            portfolio_df["total_value"].iloc[-1]
            if not portfolio_df.empty
            else initial_value
        )
        total_return_pct = (final_value / initial_value - 1) * 100
        buy_and_hold_return_pct = (
            (df["Close"].iloc[-1] / df["Close"].iloc[0] - 1) * 100
            if not df.empty
            else 0
        )

        peak = portfolio_df["total_value"].cummax()
        drawdown = (portfolio_df["total_value"] - peak) / peak
        max_drawdown_pct = drawdown.min() * 100 if not drawdown.empty else 0

        num_trades = len(trades_df[trades_df["exit_price"].notna()])
        win_trades = trades_df[trades_df["profit_pct"] > 0]
        win_rate = len(win_trades) / num_trades * 100 if num_trades > 0 else 0

        daily_returns = portfolio_df["total_value"].pct_change().dropna()
        sharpe_ratio = (
            (daily_returns.mean() / daily_returns.std()) * np.sqrt(365)
            if not daily_returns.empty and daily_returns.std() != 0
            else 0
        )

        calmar_ratio = (
            total_return_pct / abs(max_drawdown_pct) if max_drawdown_pct != 0 else 0
        )

        summary = {
            "Initial Capital": f"${initial_value:,.2f}",
            "Final Portfolio Value": f"${final_value:,.2f}",
            "Total Return (%)": f"{total_return_pct:.2f}",
            "Buy & Hold Return (%)": f"{buy_and_hold_return_pct:.2f}",
            "Max Drawdown (MDD) (%)": f"{max_drawdown_pct:.2f}",
            "Number of Trades": num_trades,
            "Win Rate (%)": f"{win_rate:.2f}",
            "Sharpe Ratio": f"{sharpe_ratio:.2f}",
            "Calmar Ratio (Return/MDD)": f"{calmar_ratio:.2f}",
        }

        return {
            "summary": summary,
            "trades": trades_df,
            "portfolio_history": portfolio_df,
            "event_log": self.event_log,
        }

    @staticmethod
    def print_summary(report: dict):
        """계산된 성과 리포트를 콘솔에 예쁘게 출력합니다."""
        print("\n--- Backtesting Results ---")
        summary = report.get("summary", {})
        for key, value in summary.items():
            print(f"{key:<25}: {value}")

        print("\n--- Trades Log ---")
        trades_df = report.get("trades")
        if trades_df is None or trades_df.empty:
            print("No trades were made.")
        else:
            print(trades_df.to_string(index=False))

        print("\n--- Event Log ---")
        event_log = report.get("event_log", [])
        if not event_log:
            print("No events.")
        else:
            for event in event_log:
                print(event)
        print("\n-----------------------\n")
