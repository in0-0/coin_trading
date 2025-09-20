# Coin Trading Bot

This is a Python-based cryptocurrency trading bot that uses the Binance API to execute trades.

## Project Structure

The project is structured as follows:

-   `live_trader_gpt.py`: The main entry point for the live trading bot.
-   `binance_data.py`: Handles data fetching from the Binance API.
-   `state_manager.py`: Manages the state of the trading bot, including open positions.
-   `models.py`: Contains the data models for the application (Signal, Position, PositionAction, PositionLeg).
-   `strategies/`: This directory contains the different trading strategies.
    -   `base_strategy.py`: Defines the interface for all strategies (supports get_position_action for advanced features).
    -   `atr_trailing_stop_strategy.py`: Advanced strategy with pyramiding, trailing stops, and partial exits.
-   `data_providers/`: Strategy pattern for fetching klines (default: `binance_klines_strategy.py`).
-   `trader/`: Trader components used by the live trader.
    -   `notifier.py`: Telegram notifications.
    -   `position_sizer.py`: Position sizing with Kelly criterion.
    -   `trade_executor.py`: Order execution with slippage guards and retries.
    -   `trade_logger.py`: File-based logging for orders, fills, trades, and final performance.
    -   `performance_calculator.py`: Calculates comprehensive trading performance metrics.
    -   `position_manager.py`: Pyramiding and averaging down strategies.
    -   `trailing_stop_manager.py`: ATR-based dynamic trailing stops.
    -   `partial_exit_manager.py`: Progressive profit taking with partial exits.
    -   `risk_manager.py`: Initial bracket calculation (SL/TP).
    -   `symbol_rules.py`: Symbol-specific parameter overrides.
-   `strategy_factory.py`: A factory for creating strategy objects.
-   `improved_strategy_factory.py`: Enhanced strategy factory with dependency injection and validation.
-   `core/`: Core modules for improved architecture.
    -   `error_handler.py`: Unified error handling system with recovery strategies.
    -   `data_models.py`: Pydantic V2 models for data validation and type safety.
    -   `dependency_injection.py`: Dependency injection container and configuration management.
    -   `position_manager.py`: Position responsibility separation with calculator and state manager.
-   `binance_data_improved.py`: Enhanced Binance data provider with strong validation.
-   `improved_live_trader.py`: Refactored live trader with improved architecture.
-   `tests/`: Contains comprehensive unit tests (17+ tests covering advanced features).
-   `data/`: Contains historical market data.
-   `backtest_logs/`: Backtest logs and outputs.
-   `_archive/`: Contains old files that are no longer in use.

## Design Patterns

The project uses the following design patterns:

-   **Strategy Pattern**: The trading logic is encapsulated in different strategy classes, which can be easily swapped. This is implemented in the `strategies` directory.
-   **Factory Pattern**: A factory is used to create strategy objects, decoupling the `LiveTrader` from the concrete strategy implementations. This is implemented in the `strategy_factory.py` file.
-   **Dependency Injection**: Centralized configuration and dependency management through a container pattern. Implemented in `core/dependency_injection.py`.
-   **Error Handler Pattern**: Unified error handling with recovery strategies and context-aware logging. Implemented in `core/error_handler.py`.
-   **Single Responsibility Principle**: Position management split into calculator, state manager, and service classes. Implemented in `core/position_manager.py`.
-   **Data Validation Pattern**: Pydantic V2 models for runtime type checking and data validation. Implemented in `core/data_models.py`.

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
-   Test improved components: `uv run pytest tests/test_improved_components.py -v`
-   Run original trader: `uv run python live_trader_gpt.py`
-   Run improved trader: `uv run python improved_live_trader.py`

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

## Advanced Position Management (고급 포지션 관리)

이 시스템은 기본적인 매수/매도 이상의 고급 포지션 관리 기능을 제공합니다:

### 주요 기능

#### 1. 불타기 (Pyramiding)
- **조건**: 3% 이상 수익 시 활성화
- **횟수**: 최대 3회까지 추가 매수 가능
- **간격**: 추가 매수 간 1시간 최소 간격
- **위험 관리**: 각 레그별 사이즈 점진적 조정

#### 2. 물타기 (Averaging Down)
- **조건**: -5% 이상 손실 시 활성화
- **횟수**: 최대 2회까지 추가 매수 가능
- **목적**: 평단가 낮춰 손실 완화
- **위험 관리**: 최대 손실 제한

#### 3. 트레일링 스탑 (Trailing Stop)
- **활성화**: 2% 이상 수익 시 자동 활성화
- **방식**: ATR 기반 동적 계산
- **특징**: 최고가 업데이트 시 스탑 상향 조정
- **보호**: 손실 구간에서는 작동하지 않음

#### 4. 부분 청산 (Partial Exits)
- **레벨**: 5%, 10%, 15%, 20% 수익 구간
- **비율**: 각 레벨별 30-40% 부분 청산
- **중복 방지**: 한 번 청산한 레벨은 재실행하지 않음
- **목적**: 단계적 이익 실현

### 작동 방식

1. **전략 분석**: ATRTrailingStopStrategy가 시장 데이터 분석
2. **액션 결정**: 적절한 포지션 관리 액션 선택
3. **실행**: LiveTrader가 액션 처리 → 실제 주문 실행
4. **상태 관리**: 모든 변경사항 저장 및 실시간 알림

### 안전성

- **위험 우선**: 모든 기능은 안전장치와 함께 구현
- **점진적 위험**: 불타기/물타기 한도 설정
- **실시간 모니터링**: 모든 액션에 대한 로깅 및 알림
- **기존 호환성**: 모든 기존 기능 완벽 호환 유지

### 활성화

기본적으로 모든 고급 기능이 활성화되어 있습니다. ATRTrailingStopStrategy를 사용하는 경우:

```bash
export STRATEGY_NAME=atr_trailing_stop
export EXECUTION_TIMEFRAME=5m
uv run python live_trader_gpt.py
```

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

-   Base directory: `LIVE_LOG_DIR` (default `live_logs`)
-   By default, logs are grouped by date: `LIVE_LOG_DIR/<YYYYMMDD>/<RUN_ID>/`.
-   To disable date partitioning, set `LIVE_LOG_DATE_PARTITION=0`.
-   Files written:
    -   `orders.csv` (ts, mode, symbol, side, price, qty, quote_qty, client_order_id)
    -   `fills.csv` (ts, mode, symbol, side, price, qty, fee, fee_asset, order_id, client_order_id)
    -   `trades.csv` (ts, mode, symbol, entry_price, exit_price, qty, pnl, pnl_pct)
    -   `events.log` (ts, mode, message)
    -   `final_performance.json` (comprehensive performance metrics on shutdown)

### Final Performance Report (`final_performance.json`)

Generated automatically when the trader shuts down (SIGINT/SIGTERM or normal exit). Contains comprehensive performance metrics:

-   **Portfolio metrics**: Final equity, total return %, realized/unrealized PnL
-   **Trade statistics**: Total trades, win rate, profit factor, average win/loss
-   **Risk metrics**: Sharpe ratio, maximum drawdown
-   **Position info**: Open positions count and symbols
-   **Session info**: Timestamp, mode (SIMULATED/LIVE), log directory

Example structure:
```json
{
  "timestamp": "2024-01-15T10:30:00.000Z",
  "mode": "SIMULATED",
  "final_equity": 1050.0,
  "total_return_pct": 5.0,
  "total_trades": 25,
  "win_rate": 64.0,
  "profit_factor": 1.8,
  "sharpe_ratio": 1.2,
  "open_positions_count": 0,
  "log_directory": "live_logs/20240115/20240115_103000_atr_trailing_stop"
}
```

This enables tracking strategy performance over time and comparing different runs.

Partial fills: multiple rows appear in `fills.csv` with the same `client_order_id`. Aggregated average price and total quantity are reflected in notifications and position state.

### Backtest Artifacts (`backtest_logs/<run_id>/`)

-   `summary.json` includes keys:
    -   `iterations`, `trades`, `pnl`
    -   `win_rate_p`, `avg_win`, `avg_loss`, `payoff_b`, `expectancy`
    -   `kelly_inputs`: `{ "p": win_rate_p, "b": payoff_b }`
-   `equity.csv`: time series of equity
-   `trades.csv`: backtest trade rows (header may exist even if empty)

## Improved Architecture (Code Quality & Structure Refactoring)

The project includes a comprehensive refactoring (TODO #11) focused on code quality and architectural improvements:

### Key Improvements

#### 1. Unified Error Handling (`core/error_handler.py`)
- **Centralized Error Processing**: All errors are handled through a single system with context-aware logging
- **Recovery Strategies**: Automatic recovery for common error types (network, data, strategy errors)
- **Context Preservation**: Rich error context including operation, symbol, and metadata
- **Notification Integration**: Automatic user notifications for critical errors

#### 2. Data Validation & Type Safety (`core/data_models.py`)
- **Pydantic V2 Models**: Runtime type checking and data validation
- **Strong Typing**: Decimal precision for financial data, datetime validation
- **Business Rules**: Automatic validation of price consistency, time ordering
- **Schema Evolution**: Extensible models for future enhancements

#### 3. Dependency Injection (`core/dependency_injection.py`)
- **Configuration Management**: Centralized environment variable handling
- **Service Container**: Lazy initialization and dependency management
- **Environment Validation**: Automatic validation of required configurations
- **Strategy Configuration**: Per-symbol strategy parameter management

#### 4. Position Responsibility Separation (`core/position_manager.py`)
- **PositionCalculator**: Pure calculation logic (average price, P&L, etc.)
- **PositionStateManager**: State management and validation
- **PositionService**: High-level business logic orchestration
- **Data Integrity**: Comprehensive validation and error handling

#### 5. Enhanced Strategy Factory (`improved_strategy_factory.py`)
- **Validation**: Strategy-specific parameter validation
- **Configuration Injection**: Automatic dependency resolution
- **Extensibility**: Easy registration of new strategies
- **Error Handling**: Clear error messages with context

#### 6. Improved Data Provider (`binance_data_improved.py`)
- **Strong Validation**: Pydantic models for all API responses
- **Error Context**: Detailed error information for debugging
- **Data Integrity**: Automatic data consistency checks
- **Recovery Mechanisms**: Fallback strategies for data issues

### Architecture Benefits

1. **Maintainability**: Clear separation of concerns and single responsibility
2. **Testability**: Isolated components with dependency injection
3. **Reliability**: Comprehensive error handling and recovery
4. **Type Safety**: Runtime validation prevents data corruption
5. **Extensibility**: Easy to add new strategies and components
6. **Observability**: Rich logging and error context for debugging

### Migration Path

The improved architecture is backward compatible. You can:

1. **Continue using original components**: All existing code continues to work
2. **Gradually migrate**: Replace components one by one
3. **Use improved versions**: Run `uv run python improved_live_trader.py` for the new architecture

### Testing

Comprehensive test suite for all improved components:

```bash
uv run pytest tests/test_improved_components.py -v
```

17 tests covering error handling, data validation, position management, and integration scenarios.

### Legacy Code Cleanup

The project has been cleaned up to remove duplicate and unused legacy code:

- **core/configuration.py** → moved to `_archive/legacy_configuration.py`
- **core/constants.py** → moved to `_archive/legacy_constants.py`
- **core/signal.py** → moved to `_archive/legacy_signal.py`
- **tests/test_configuration.py** → moved to `_archive/test_legacy_configuration.py`
- **refactor_todo.md** → moved to `_archive/legacy_refactor_todo.md`

All imports have been updated to use the improved components:
- `core.dependency_injection.get_config()` instead of `Configuration` class
- `models.Signal` instead of `core.signal.Signal`
- Improved error handling and data validation throughout the codebase

## CI

GitHub Actions workflow runs Ruff and Pytest on every push and PR. See `.github/workflows/ci.yml`.
