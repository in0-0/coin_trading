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

## CI

GitHub Actions workflow runs Ruff and Pytest on every push and PR. See `.github/workflows/ci.yml`.
