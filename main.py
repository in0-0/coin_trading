import os
import datetime
from dotenv import load_dotenv
from binance_data import BinanceData
from strategy import StrategyFactory
from backtester import Backtester
from config import STRATEGY_CONFIG, TRADE_SETTINGS, BACKTEST_SETTINGS

def main():
    # .env 파일에서 환경 변수 로드
    load_dotenv()
    api_key = os.environ.get('BINANCE_API_KEY')
    secret_key = os.environ.get('BINANCE_SECRET_KEY')

    if not api_key or not secret_key:
        print("Error: Please set BINANCE_API_KEY and BINANCE_SECRET_KEY in a .env file.")
        return

    # --- 사용할 전략 선택 ---
    strategy_name = "ma_cross"

    # --- 설정 로드 ---
    config = STRATEGY_CONFIG.get(strategy_name)
    if config is None:
        print(f"Error: Strategy '{strategy_name}' not found in STRATEGY_CONFIG.")
        return
    strategy_params = config.get("params", {})
    signal_meaning = config.get("signal_meaning", {})

    symbol = TRADE_SETTINGS.get("symbol", "BTCUSDT")
    interval = TRADE_SETTINGS.get("interval")
    start_date = TRADE_SETTINGS.get("start_date", "1 year ago UTC")
    initial_capital = BACKTEST_SETTINGS.get("initial_capital", 10000)

    # --- 초기화 ---
    binance_data = BinanceData(api_key, secret_key)
    strategy_factory = StrategyFactory()
    backtester = Backtester(initial_capital)

    # 팩토리에서 전략 객체 생성
    try:
        strategy = strategy_factory.get_strategy(strategy_name, **strategy_params)
    except ValueError as e:
        print(e)
        return

    # --- 데이터 가져오기 및 전략 적용 ---
    print(f"Fetching data for {symbol} with interval {interval} from {start_date}...")
    df = binance_data.get_historical_data(symbol, interval, start_date)
    result_df = strategy.apply_strategy(df)

    # --- 백테스팅 실행 ---
    backtester.run(result_df)

    # --- 리포트 파일로 저장 ---
    log_dir = "backtest_logs"
    os.makedirs(log_dir, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    file_name = f"{log_dir}/{timestamp}_{strategy_name}_{symbol}.txt"
    
    report_content = backtester.get_report_string(strategy_name, symbol, interval)
    
    with open(file_name, "w", encoding="utf-8") as f:
        f.write(report_content)
    print(f"\nBacktest report saved to: {file_name}")

    # --- 결과 일부 콘솔 출력 ---
    print(f"\n--- Strategy Signal Details for {strategy_name} ---")
    print("Signal Meaning:", signal_meaning)
    print(result_df.tail(10))

if __name__ == "__main__":
    main()
