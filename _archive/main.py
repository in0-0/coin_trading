import datetime
import os

import config
from backtester import Backtester
from dotenv import load_dotenv
from live_trader import TradingBot
from position_sizer import PositionSizerFactory
from strategy import StrategyFactory

from binance_data import BinanceData


def run_all_backtests():
    """설정된 모든 전략과 코인에 대해 백테스팅을 실행합니다."""
    print("--- Starting in Backtest Mode ---")

    initial_capital = config.BACKTEST_SETTINGS.get("initial_capital", 10000.0)
    start_date = config.BACKTEST_SETTINGS.get("start_date", "1 year ago UTC")
    symbols = config.BACKTEST_SETTINGS.get("symbols", ["BTCUSDT"])
    interval = config.BACKTEST_SETTINGS.get("interval")
    strategies = config.STRATEGY_CONFIG.keys()

    for strategy_name in strategies:
        for symbol in symbols:
            run_single_backtest(
                strategy_name, symbol, interval, start_date, initial_capital
            )


def run_single_backtest(
    strategy_name: str,
    symbol: str,
    interval: str,
    start_date: str,
    initial_capital: float,
):
    """지정된 단일 전략으로 백테스팅을 실행하고 결과를 출력합니다."""
    print(f"\n{'=' * 50}")
    print(f"Running backtest for strategy: {strategy_name}")
    print(f"Symbol: {symbol}, Interval: {interval}, Start Date: {start_date}")
    print(f"{'=' * 50}")

    # --- 전략 설정 로드 ---
    strategy_config = config.STRATEGY_CONFIG.get(strategy_name)
    if not strategy_config:
        print(f"Error: Strategy '{strategy_name}' not found in STRATEGY_CONFIG.")
        return

    strategy_params = strategy_config.get("params", {})
    exit_params = strategy_config.get("exit_params", {})
    position_sizer_config = strategy_config.get("position_sizer", {"name": "all_in"})

    # --- 데이터 가져오기 ---
    binance_data = BinanceData(api_key=config.API_KEY, secret_key=config.SECRET_KEY)
    try:
        df = binance_data.get_historical_data(symbol, interval, start_date)
    except Exception as e:
        print(f"Error fetching data for {symbol}: {e}")
        return

    # --- 전략 적용 ---
    strategy = StrategyFactory().get_strategy(strategy_name, **strategy_params)
    df_strategy = strategy.apply_strategy(df.copy())

    # --- 포지션 사이저 생성 ---
    position_sizer = PositionSizerFactory().get_sizer(
        position_sizer_config.get("name", "all_in"),
        **position_sizer_config.get("params", {}),
    )

    # --- 백테스팅 실행 ---
    backtester = Backtester(initial_capital, position_sizer)
    report = backtester.run(df_strategy, **exit_params)

    # --- 결과 출력 및 저장 ---
    backtester.print_summary(report)
    save_report(report, strategy_name, symbol, interval, start_date)


def save_report(
    report: dict, strategy_name: str, symbol: str, interval: str, start_date: str
):
    """백테스팅 결과를 파일로 저장합니다."""
    log_dir = "backtest_logs"
    os.makedirs(log_dir, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    file_name = f"{log_dir}/{timestamp}_{strategy_name}_{symbol}.txt"

    with open(file_name, "w", encoding="utf-8") as f:
        f.write(f"Strategy: {strategy_name}\n")
        f.write(f"Symbol: {symbol}\n")
        f.write(f"Interval: {interval}\n")
        f.write(f"Start Date: {start_date}\n")
        f.write("\n--- Summary ---\n")
        for key, value in report["summary"].items():
            f.write(f"{key}: {value}\n")
        f.write("\n--- Trades ---\n")
        f.write(report["trades"].to_string())
        f.write("\n\n--- Event Log ---\n")
        for event in report["event_log"]:
            f.write(f"{event}\n")
        f.write("\n\n--- Portfolio History ---\n")
        f.write(report["portfolio_history"].to_string())

    print(f"Report saved to {file_name}")


def run_live_trading():
    """실시간 거래 봇을 실행합니다."""
    bot = TradingBot()
    bot.run()


def main():
    """메인 실행 함수"""
    load_dotenv()

    if not config.API_KEY or not config.SECRET_KEY:
        print(
            "Error: Please set BINANCE_API_KEY and BINANCE_SECRET_KEY in a .env file."
        )
        return

    if config.MODE == "backtest":
        run_all_backtests()
    elif config.MODE == "live":
        run_live_trading()
    else:
        print(
            f"Error: Invalid MODE '{config.MODE}' in config.py. Use 'backtest' or 'live'."
        )


if __name__ == "__main__":
    main()
