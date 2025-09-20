# 코인 트레이딩 봇

이 저장소는 바이낸스 API를 사용해 트레이드를 실행할 수 있는 파이썬 기반 암호화폐 트레이딩 봇입니다.

## 프로젝트 구조

다음과 같이 구성되어 있습니다:

- `live_trader_gpt.py`: 라이브 트레이딩 봇의 메인 엔트리포인트
- `binance_data.py`: 바이낸스 API에서 데이터 수집/갱신 및 CSV 영속화
- `state_manager.py`: 오픈 포지션 등 봇 상태 관리
- `models.py`: 앱에서 사용하는 데이터 모델
- `strategies/`: 다양한 트레이딩 전략 구현 디렉터리
  - `base_strategy.py`: 모든 전략의 인터페이스 정의 (get_position_action 고급 기능 지원)
  - `atr_trailing_stop_strategy.py`: 고급 전략 (불타기, 트레일링 스톱, 부분 청산 포함)
- `data_providers/`: Klines 페칭을 위한 전략 패턴 디렉터리(기본: `binance_klines_strategy.py`)
- `trader/`: 라이브 트레이더가 사용하는 컴포넌트들
  - `notifier.py`: 텔레그램 알림
  - `position_sizer.py`: Kelly 기준 포지션 사이징
  - `trade_executor.py`: 슬리피지 가드 및 재시도 포함 주문 실행
  - `trade_logger.py`: 주문/체결/트레이드 파일 기반 로깅
  - `position_manager.py`: 불타기와 물타기 전략
  - `trailing_stop_manager.py`: ATR 기반 동적 트레일링 스탑
  - `partial_exit_manager.py`: 단계별 부분 청산
  - `risk_manager.py`: 초기 브래킷 계산 (SL/TP)
  - `symbol_rules.py`: 심볼별 파라미터 오버라이드
- `strategy_factory.py`: 전략 객체 생성을 담당하는 팩토리
- `tests/`: 포괄적 단위 테스트 (고급 기능 포함 17개+ 테스트)
- `data/`: 히스토리컬 마켓 데이터 CSV
- `backtest_logs/`: 백테스트 로그 및 결과 아티팩트
- `_archive/`: 더 이상 사용하지 않는 과거 파일 보관

## 디자인 패턴

- **Strategy 패턴**: 트레이딩 로직을 전략 클래스로 캡슐화하여 손쉽게 교체할 수 있습니다(`strategies/`).
- **Factory 패턴**: `LiveTrader`가 구체 전략 구현에 의존하지 않도록 팩토리를 통해 전략을 생성합니다(`strategy_factory.py`).

## 셋업

- Python 3.12 및 `uv` 설치
- 의존성 동기화(기본 + 개발):

```bash
uv sync --all-extras --dev
```

- 환경 템플릿 복사 후 값 채우기:

```bash
cp .env.sample .env
```

## 환경 변수

- **MODE**: `TESTNET` 또는 `REAL`
- **TESTNET_BINANCE_API_KEY**, **TESTNET_BINANCE_SECRET_KEY**
- **BINANCE_API_KEY**, **BINANCE_SECRET_KEY**
- **TELEGRAM_BOT_TOKEN**, **TELEGRAM_CHAT_ID** (옵션)
- **SYMBOLS**(콤마 구분), **EXEC_INTERVAL_SECONDS**, **LOG_FILE**
- 실행(주문): **ORDER_EXECUTION**(`SIMULATED`|`LIVE`, 기본 `SIMULATED`), **MAX_SLIPPAGE_BPS**(기본 `50`), **ORDER_TIMEOUT_SEC**(기본 `10`), **ORDER_RETRY**(기본 `3`), **ORDER_KILL_SWITCH**(`true`/`false`, 기본 `false`)
- 라이브 로그: **LIVE_LOG_DIR**(기본 `live_logs`), **RUN_ID**(기본: 타임스탬프 + 전략명)

- 전략 선택:
  - **STRATEGY_NAME**: `atr_trailing_stop`(기본) 또는 `composite_signal`
  - **EXECUTION_TIMEFRAME**: 예) `5m`, `15m`, `1h`
- Composite 전략(Kelly 포함) 파라미터:
  - **BRACKET_K_SL**: 초기 손절을 위한 ATR 배수(기본 `1.5`)
  - **BRACKET_RR**: 테이크프로핏을 위한 R/R 비(기본 `2.0`)
  - **KELLY_FMAX**: Kelly 최대 비중 캡(기본 `0.2`)
  - 심볼별 오버라이드는 `trader/symbol_rules.py`의 `COMPOSITE_PARAM_OVERRIDES`에서 설정 가능

## 커맨드

- 린트: `uv run ruff check .`
- 린트(자동 수정): `uv run ruff check --fix .`
- 테스트: `uv run pytest -q`
- 트레이더 실행: `uv run python live_trader_gpt.py`

## 실행 모드 (TESTNET vs REAL)

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

- 현재 버전은 매수/매도 시 실제 주문 API를 호출하지 않고 포지션만 로컬에 기록합니다. 실체결 활성화는 `TODO.md`의 "실거래 주문 실행" 항목 완료가 필요합니다.
- TESTNET 모드에서는 테스트넷 REST URL(`https://testnet.binance.vision/api`)을 사용합니다.
- 안전 종료: Ctrl+C → 모든 보유 포지션을 로컬 상태에서 정리하고 종료합니다.

### 주문 실행 모드

- `ORDER_EXECUTION=SIMULATED`(기본): 현재와 동일한 시뮬레이션 기록만 수행
- `ORDER_EXECUTION=LIVE`: 실제 Binance 주문 API 호출 준비. `ORDER_KILL_SWITCH=true`이면 모든 LIVE 주문이 차단됩니다.

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

## Composite 전략 (Signal + Kelly)

Composite 전략은 EMA, 볼린저밴드, RSI, MACD, 거래량, OBV를 단일 점수 S ∈ [-1, 1]로 결합합니다.

- 전략 활성화 예:

```bash
export STRATEGY_NAME=composite_signal
export EXECUTION_TIMEFRAME=5m
# Optional bracket/kelly params
export BRACKET_K_SL=1.5
export BRACKET_RR=2.0
export KELLY_FMAX=0.2
```

- 라이브 트레이더 동작:
  - `score()`를 통해 신뢰도 → Kelly 기반 노치널 사이징
  - ATR로 초기 브래킷 계산: SL = 진입 - k_sl·ATR, TP = 진입 + rr·k_sl·ATR
  - 매수 알림에 포함: S, Confidence, f* (Kelly), ATR, SL/TP
  - 안전장치: 슬리피지 가드(`MAX_SLIPPAGE_BPS`), 최소 노치널, 로트 사이즈 반올림, 킬 스위치

- 심볼별 파라미터 오버라이드:
  - `trader/symbol_rules.py`의 `COMPOSITE_PARAM_OVERRIDES` 수정 또는 코드에서 `resolve_composite_params()` 사용

### TESTNET에서 Composite 실행

```bash
export MODE=TESTNET
export TESTNET_BINANCE_API_KEY=...; export TESTNET_BINANCE_SECRET_KEY=...
export STRATEGY_NAME=composite_signal
export EXECUTION_TIMEFRAME=5m
export ORDER_EXECUTION=SIMULATED   # 검증 전까지는 시뮬레이션 권장
uv run python live_trader_gpt.py
```

### REAL에서 Composite 실행(가드 포함)

```bash
export MODE=REAL
export BINANCE_API_KEY=...; export BINANCE_SECRET_KEY=...
export STRATEGY_NAME=composite_signal
export EXECUTION_TIMEFRAME=5m
export ORDER_EXECUTION=LIVE
export ORDER_KILL_SWITCH=true     # 초기에는 드라이런 용도로 ON 권장
export MAX_SLIPPAGE_BPS=50
uv run python live_trader_gpt.py
```

## 백테스트(Composite)

클로즈된 캔들만 사용하며 룩어헤드가 없는 최소 기능 백테스트를 제공합니다. `df.iloc[:i]` 윈도우를 전략에 전달하고 수수료/슬리피지를 고려할 수 있습니다. 예시:

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

메모:

- 클로즈된 캔들만 사용하세요. 인디케이터 내부에서는 `dropna()`가 호출됩니다.
- 수수료/슬리피지는 bps 단위로 설정 가능. 향후 `backtest_logs/`에 PnL/트레이드 로그와 Kelly 입력(p, avg_win, avg_loss) 집계가 추가될 예정입니다.

## 로깅 & 아티팩트

### 라이브/시뮬레이션 로그(`TradeLogger`)

- 기본 디렉터리: `LIVE_LOG_DIR`(기본 `live_logs`), 각 실행은 `LIVE_LOG_DIR/<RUN_ID>/` 하위에 저장됩니다.
- 생성 파일:
  - `orders.csv` (ts, mode, symbol, side, price, qty, quote_qty, client_order_id)
  - `fills.csv` (ts, mode, symbol, side, price, qty, fee, fee_asset, order_id, client_order_id)
  - `trades.csv` (ts, mode, symbol, entry_price, exit_price, qty, pnl, pnl_pct)
  - `events.log` (ts, mode, message)

부분 체결: 동일한 `client_order_id`로 `fills.csv`에 여러 행이 기록됩니다. 알림 및 포지션 상태에는 평균가격/총 수량이 집계되어 반영됩니다.

### 백테스트 아티팩트(`backtest_logs/<run_id>/`)

- `summary.json` 키:
  - `iterations`, `trades`, `pnl`
  - `win_rate_p`, `avg_win`, `avg_loss`, `payoff_b`, `expectancy`
  - `kelly_inputs`: `{ "p": win_rate_p, "b": payoff_b }`
- `equity.csv`: 자산 곡선 시계열
- `trades.csv`: 백테스트 트레이드 행(비어있어도 헤더는 존재할 수 있음)

## CI

GitHub Actions 워크플로는 모든 푸시/PR에서 Ruff와 Pytest를 실행합니다. 워크플로 파일은 `.github/workflows/ci.yml`을 참고하세요.


