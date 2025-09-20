# Coin Trading Bot

This is a Python-based cryptocurrency trading bot that uses the Binance API to execute trades.

## Project Structure

The project is structured as follows:

-   `live_trader_gpt.py`: The main entry point for the live trading bot.
-   `binance_data.py`: Handles data fetching from the Binance API.
-   `state_manager.py`: Manages the state of the trading bot, including open positions.
-   `models.py`: Contains the data models for the application.
-   `strategies/`: This directory contains the different trading strategies.
    -   `base_strategy.py`: Defines the interface for all strategies.
    -   `atr_trailing_stop_strategy.py`: A concrete implementation of a trading strategy.
-   `data_providers/`: Strategy pattern for fetching klines (default: `binance_klines_strategy.py`).
-   `trader/`: Trader components used by the live trader (`notifier.py`, `position_sizer.py`, `trade_executor.py`).
-   `strategy_factory.py`: A factory for creating strategy objects.
-   `tests/`: Contains unit tests for the project.
-   `data/`: Contains historical market data.
-   `backtest_logs/`: Backtest logs and outputs.
-   `_archive/`: Contains old files that are no longer in use.

## Design Patterns

The project uses the following design patterns:

-   **Strategy Pattern**: The trading logic is encapsulated in different strategy classes, which can be easily swapped. This is implemented in the `strategies` directory.
-   **Factory Pattern**: A factory is used to create strategy objects, decoupling the `LiveTrader` from the concrete strategy implementations. This is implemented in the `strategy_factory.py` file.

## Setup

-   Install Python 3.12 and `uv`.
-   Sync dependencies (default + dev):

    ```bash
    uv sync --all-extras --dev
    ```

-   Copy environment template and fill values:

    ```bash
    cp .env.sample .env
    ```

## Environment Variables

-   **MODE**: `TESTNET` or `REAL`
-   **TESTNET_BINANCE_API_KEY**, **TESTNET_BINANCE_SECRET_KEY**
-   **BINANCE_API_KEY**, **BINANCE_SECRET_KEY**
-   **TELEGRAM_BOT_TOKEN**, **TELEGRAM_CHAT_ID** (optional)
-   **SYMBOLS** (comma-separated), **EXEC_INTERVAL_SECONDS**, **LOG_FILE**
 -   Execution (orders): **ORDER_EXECUTION** (`SIMULATED`|`LIVE`, default `SIMULATED`), **MAX_SLIPPAGE_BPS** (default `50`), **ORDER_TIMEOUT_SEC** (default `10`), **ORDER_RETRY** (default `3`), **ORDER_KILL_SWITCH** (`true`/`false`, default `false`)
 -   Live logs: **LIVE_LOG_DIR** (default `live_logs`), **RUN_ID** (default timestamp + strategy)

-   Strategy selection:
    -   **STRATEGY_NAME**: `atr_trailing_stop` (default) or `composite_signal`
    -   **EXECUTION_TIMEFRAME**: e.g., `5m`, `15m`, `1h`
-   Composite strategy (Signal + Kelly) parameters:
    -   **BRACKET_K_SL**: ATR multiplier for initial stop (default `1.5`)
    -   **BRACKET_RR**: Risk/Reward ratio for take-profit (default `2.0`)
    -   **KELLY_FMAX**: Max Kelly fraction cap (default `0.2`)
    -   Per-symbol overrides are supported via `trader/symbol_rules.py` `COMPOSITE_PARAM_OVERRIDES`

## Commands

-   Lint: `uv run ruff check .`
-   Lint (fix): `uv run ruff check --fix .`
-   Test: `uv run pytest -q`
-   Run trader: `uv run python live_trader_gpt.py`

## Run Modes (TESTNET vs REAL)

### TESTNET 실행
- 환경 변수: `MODE=TESTNET`, `TESTNET_BINANCE_API_KEY`, `TESTNET_BINANCE_SECRET_KEY`
- 선택: `SYMBOLS`, `EXEC_INTERVAL_SECONDS`, `LOG_FILE`, `TELEGRAM_*`
- 실행:

```bash
uv run python live_trader_gpt.py
# 또는
uv run run_trader
```

예시 `.env`:

```bash
MODE=TESTNET
TESTNET_BINANCE_API_KEY=your_testnet_key
TESTNET_BINANCE_SECRET_KEY=your_testnet_secret
SYMBOLS=BTCUSDT,ETHUSDT,BNBUSDT,SOLUSDT,XRPUSDT
EXEC_INTERVAL_SECONDS=60
LOG_FILE=live_trader.log
# Optional
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
# Order execution (optional; default is safe SIMULATED)
ORDER_EXECUTION=SIMULATED
MAX_SLIPPAGE_BPS=50
ORDER_TIMEOUT_SEC=10
ORDER_RETRY=3
ORDER_KILL_SWITCH=false
```

### REAL 실행
- 환경 변수: `MODE=REAL`, `BINANCE_API_KEY`, `BINANCE_SECRET_KEY`
- 선택: 위와 동일
- 실행:

```bash
uv run python live_trader_gpt.py
# 또는
uv run run_trader
```

예시 `.env`:

```bash
MODE=REAL
BINANCE_API_KEY=your_mainnet_key
BINANCE_SECRET_KEY=your_mainnet_secret
SYMBOLS=BTCUSDT,ETHUSDT,BNBUSDT,SOLUSDT,XRPUSDT
EXEC_INTERVAL_SECONDS=60
LOG_FILE=live_trader.log
# Optional
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
# Order execution (recommend keeping SIMULATED until fully verified)
ORDER_EXECUTION=SIMULATED
MAX_SLIPPAGE_BPS=50
ORDER_TIMEOUT_SEC=10
ORDER_RETRY=3
ORDER_KILL_SWITCH=false
```

### 동작 메모
- 현재 버전은 매수/매도 시 실제 주문 API를 호출하지 않고 포지션만 로컬에 기록합니다. 실체결 활성화는 `TODO.md`의 "실거래 주문 실행" 항목을 완료해야 합니다.
- TESTNET 모드에서는 테스트넷 REST URL(`https://testnet.binance.vision/api`)을 사용합니다.
- 안전 종료: Ctrl+C → 모든 보유 포지션을 로컬 상태에서 정리하고 종료합니다.

### 주문 실행 모드
- `ORDER_EXECUTION=SIMULATED` (기본): 현재와 동일한 시뮬레이션 기록만 수행
- `ORDER_EXECUTION=LIVE`: 실제 Binance 주문 API를 호출할 준비를 합니다. 본 저장소는 순차 작업으로 점진적으로 라이브 주문 로직을 추가합니다. `ORDER_KILL_SWITCH=true`이면 모든 LIVE 주문이 차단됩니다.

## Composite Strategy (Signal + Kelly)

The composite strategy blends EMA, BB, RSI, MACD, Volume, and OBV into a single score S ∈ [-1,1].

-   Enable composite strategy:

    ```bash
    export STRATEGY_NAME=composite_signal
    export EXECUTION_TIMEFRAME=5m
    # Optional bracket/kelly params
    export BRACKET_K_SL=1.5
    export BRACKET_RR=2.0
    export KELLY_FMAX=0.2
    ```

-   Live trader behavior:
    -   Uses `score()` for confidence → Kelly-based notional sizing
    -   Computes initial bracket via ATR: SL = entry - k_sl·ATR, TP = entry + rr·k_sl·ATR
    -   Buy notifications include: S, Confidence, f* (Kelly), ATR, SL/TP
    -   Safety: slippage guard (`MAX_SLIPPAGE_BPS`), min notional, lot size rounding, kill switch

-   Per-symbol parameter overrides:
    -   Edit `trader/symbol_rules.py` `COMPOSITE_PARAM_OVERRIDES` or use `resolve_composite_params()` in code

### Run Composite in TESTNET

```bash
export MODE=TESTNET
export TESTNET_BINANCE_API_KEY=...; export TESTNET_BINANCE_SECRET_KEY=...
export STRATEGY_NAME=composite_signal
export EXECUTION_TIMEFRAME=5m
export ORDER_EXECUTION=SIMULATED   # keep simulated until verified
uv run python live_trader_gpt.py
```

### Run Composite in REAL (with guards)

```bash
export MODE=REAL
export BINANCE_API_KEY=...; export BINANCE_SECRET_KEY=...
export STRATEGY_NAME=composite_signal
export EXECUTION_TIMEFRAME=5m
export ORDER_EXECUTION=LIVE
export ORDER_KILL_SWITCH=true     # start with kill switch ON for dry runs
export MAX_SLIPPAGE_BPS=50
uv run python live_trader_gpt.py
```

## Backtesting (Composite)

Minimal backtesting is available for closed-candle, no-lookahead runs. It iterates with `df.iloc[:i]` windows and can account for fees/slippage. Example:

```python
from binance_data import BinanceData
from strategies.composite_signal_strategy import CompositeSignalStrategy
from types import SimpleNamespace
from backtests.composite_backtest import run_backtest

data = BinanceData(api_key=None, api_secret=None)
df = data.get_and_update_klines("BTCUSDT", "5m")
config = SimpleNamespace(ema_fast=12, ema_slow=26, bb_len=20, rsi_len=14,
                         macd_fast=12, macd_slow=26, macd_signal=9,
                         atr_len=14, k_atr_norm=1.0, vol_len=20, obv_span=20,
                         max_score=1.0, buy_threshold=0.3, sell_threshold=-0.3)
strategy = CompositeSignalStrategy(config)
summary = run_backtest(df=df, strategy=strategy, warmup=50, fee_bps=10.0, slippage_bps=5.0)
print(summary)  # {"iterations": ..., "trades": 0, "pnl": 0.0}
```

Notes:
-   Use only closed candles; indicators call `dropna()` internally
-   Fees/slippage are configurable (bps). Future updates will add PnL/trade logs under `backtest_logs/` and Kelly input (p, avg_win, avg_loss) aggregation

## Logging & Artifacts

### Live/Simulated Logs (`TradeLogger`)

-   Base directory: `LIVE_LOG_DIR` (default `live_logs`), each run under `LIVE_LOG_DIR/<RUN_ID>/`.
-   Files written:
    -   `orders.csv` (ts, mode, symbol, side, price, qty, quote_qty, client_order_id)
    -   `fills.csv` (ts, mode, symbol, side, price, qty, fee, fee_asset, order_id, client_order_id)
    -   `trades.csv` (ts, mode, symbol, entry_price, exit_price, qty, pnl, pnl_pct)
    -   `events.log` (ts, mode, message)

Partial fills: multiple rows appear in `fills.csv` with the same `client_order_id`. Aggregated average price and total quantity are reflected in notifications and position state.

### Backtest Artifacts (`backtest_logs/<run_id>/`)

-   `summary.json` includes keys:
    -   `iterations`, `trades`, `pnl`
    -   `win_rate_p`, `avg_win`, `avg_loss`, `payoff_b`, `expectancy`
    -   `kelly_inputs`: `{ "p": win_rate_p, "b": payoff_b }`
-   `equity.csv`: time series of equity
-   `trades.csv`: backtest trade rows (header may exist even if empty)

## CI

GitHub Actions workflow runs Ruff and Pytest on every push and PR. See `.github/workflows/ci.yml`.
