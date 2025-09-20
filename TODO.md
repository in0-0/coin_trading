# 자동 거래 시스템 안정화 리팩토링 계획 (TODO)

본 계획은 3단계(런타임 안정화 → 테스트 정리 → 품질/CI)로 진행합니다. 현재 코드 구조와 일치하도록 파일명을 최신화했습니다.

## 1) 런타임 안정화 (Day 1)

- [x] `binance_data.py` 데이터 일관성/증분 업데이트 안정화
    - [x] 기존 CSV 로드 시 컬럼 케이스 오타 수정 (`"Open time"` 파싱 라인 수정)
    - [x] 숫자 컬럼 타입 강제(`Open/High/Low/Close/Volume`)
    - [x] `get_and_update_klines(symbol, interval)` 반환 컬럼을 `TARGET_COLUMNS`로 일관화
    - [x] 에러 로깅 및 빈 데이터 처리 보강
- [x] `models.py` 포지션 모델 고도화
    - [x] `Position`에 헬퍼 추가(`is_open()`, `is_long()`), 필드명 `stop_price`로 통일
    - [x] 직렬화/역직렬화 로직 유지 및 타입 힌트 강화
- [x] `state_manager.py` 심볼별 포지션 CRUD 추가
    - [x] `get_position(symbol)`, `upsert_position(symbol, position|None)` 구현
    - [x] 기존 `save_positions()/load_positions()`와 호환 유지
- [x] 전략 인터페이스 통일
    - [x] `strategies/base_strategy.py`: `get_signal(market_data, position) -> Signal`
    - [x] `strategies/atr_trailing_stop_strategy.py`에서 `StateManager` 직접 접근 제거, 입력 `position` 기반 판정으로 수정
    - [x] 컬럼 접근을 Title case(`Close/High/Low`)로 통일
- [x] `live_trader_gpt.py` 실행 로직 정합성
    - [x] 전략 호출 시 현재 포지션 전달: `strategy.get_signal(df, positions.get(sym))`
    - [x] BUY 시 `Position` 생성 및 `stop_price` 사용, SELL 시 포지션 제거 및 저장
    - [x] 메시지/로그에서 `stop_loss`→`stop_price` 용어 통일

## 2) 테스트 정리 (Day 2)

- [x] 레거시/손상 테스트 정리
    - [x] 삭제된 모듈 참조(`backtester.py`, `main.py`, `strategy.py`, `position_sizer.py`, `live_trader.py`) 테스트 폐기 또는 `_archive/tests`로 이동
    - [x] 손상된 `tests/test_backtester.py` 정리(보관 또는 삭제)
- [x] 신규 단위 테스트 작성/수정
    - [x] `tests/test_binance_data.py`: `get_and_update_klines`와 타입/컬럼 보장 검증(Mock 클라이언트)
    - [x] `tests/test_state_manager.py`: 심볼별 `get_position/upsert_position` 추가 검증
    - [x] `tests/test_strategy.py`: ATR 전략 신호/컬럼 케이스 검증
    - [x] `tests/test_live_trader.py`: Binance `Client` 모킹 후 엔트리/청산 플로우 검증

## 3) 품질/구조/CI (Day 3)

- [x] `pyproject.toml` 품질 도구 설정
    - [x] Ruff/pytest 설정 추가 및 dev-deps 정리
    - [x] 스크립트 추가: `lint`, `test`, `run-trader`
- [x] CI 파이프라인
    - [x] GitHub Actions 워크플로우: ruff + pytest
- [x] 문서/환경
    - [x] `README.md` 업데이트: 아키텍처/환경 변수/실행 방법
    - [x] `.env.sample` 배포

- [x] Cursor 규칙: pytest-first TDD 규칙 추가 및 테스트 잠금 ([.cursor/rules/pytest-first-tdd.mdc](mdc:.cursor/rules/pytest-first-tdd.mdc), [.cursorignore](mdc:.cursorignore))

## 주석
- 컬럼 네이밍은 `Open/High/Low/Close/Volume`(Title case)로 표준화합니다.
- 전략은 신호만 판정하고, 포지션 CRUD는 트레이더/상태관리자가 담당합니다.

## 4) 실거래 주문 실행 (Enable Live Orders)

- [x] 주문 실행 플래그/모드 추가 (`ORDER_EXECUTION`: `SIMULATED`/`LIVE`) 및 기본 `SIMULATED`
    - [x] `.env.sample`(또는 `env.example`), `README.md`에 환경변수 항목 추가 (`ORDER_EXECUTION`, `MAX_SLIPPAGE_BPS`, `ORDER_TIMEOUT_SEC`, `ORDER_RETRY`, `ORDER_KILL_SWITCH`)
    - [x] `live_trader_gpt.py`에서 환경변수 로드 및 `TradeExecutor`로 전달 (현재 executor 속성으로 보관)
    - [x] 기본값: `ORDER_EXECUTION=SIMULATED`, `MAX_SLIPPAGE_BPS=50`, `ORDER_TIMEOUT_SEC=10`, `ORDER_RETRY=3`, `ORDER_KILL_SWITCH=false`
- [x] `_place_buy_order`/`_place_sell_order`에 `client.create_order(...)` 연동 (MARKET 우선)
    - [x] `TradeExecutor`에 `execution_mode` 분기 (LIVE 실제 호출 적용)
    - [x] BUY: `quoteOrderQty` 사용, SELL: `quantity` 사용, 공통: `newOrderRespType='FULL'`
    - [x] `newClientOrderId` 아이템포턴시 적용 (재시도 시 동일 ID)
- [x] 심볼 거래 규칙 검증: LOT_SIZE, MIN_NOTIONAL, PRICE_FILTER 적용 및 수량/가격 라운딩 (헬퍼 스캐폴드 추가)
    - [x] `get_symbol_info(symbol)` 캐시, `LOT_SIZE.stepSize/minQty`, `MIN_NOTIONAL.minNotional`, `PRICE_FILTER.tickSize` 파싱 (`trader/symbol_rules.py`)
    - [x] `round_qty_to_step(qty, step)`, `validate_min_notional(price, qty, min_notional)`, `round_price_to_tick(price, tick)` 헬퍼 구현
- [x] 주문 예외 처리 강화: 타임아웃/재시도(backoff), idempotency 키, 네트워크 에러 복구
    - [x] 재시도 래퍼: 지수 백오프(+지터), `ORDER_RETRY`/`ORDER_TIMEOUT_SEC` 적용
    - [x] 실패 시 최근 주문 조회(`get_all_orders` 스캔)로 상태 확인/idempotency 보강
- [x] 주문/체결 추적: `orderId`, 상태 조회, 평균 체결가/수수료 반영, 부분체결 처리
    - [x] `FULL` 응답 기반 평균가/체결수량/수수료 집계
    - [x] 미완료 시 상태 폴링 후 집계
    - [x] 알림/로그에 `orderId`, 평균가, 체결수량, 수수료 포함
- [x] 슬리피지/체결 안전장치: 최대 허용 슬리피지, 최소 체결 금액, 킬스위치 환경변수
    - [x] 사전 가드: `get_orderbook_ticker` 스프레드/추정 슬리피지 > `MAX_SLIPPAGE_BPS`면 주문 차단
    - [x] `ORDER_KILL_SWITCH=true` 시 모든 LIVE 주문 차단 및 경고 알림 (현재 구현: LIVE 분기에서 즉시 차단)
- [x] 실시간 잔고/포지션 동기화: 체결 후 잔고 갱신, 수수료 고려한 수량 계산
    - [x] BUY: 실제 체결 수량/평균가로 `Position` 저장, 초기 `stop_price`는 ATR 기반 산출
    - [x] SELL: 실제 평균가/수수료 포함 PnL 계산, 포지션 제거/저장
- [ ] 통합 테스트: `Client.create_order` 모킹으로 엔트리/청산 플로우 검증, 규칙 위반 케이스 포함
    - [x] 유닛: 수량 라운딩/최소 주문금액/슬리피지 가드/아이템포턴시 ([tests/test_trade_executor.py](mdc:tests/test_trade_executor.py))
    - [x] 통합: 타임아웃 후 상태조회(idempotency) → 포지션 반영 ([tests/test_live_trader_orders_integration.py](mdc:tests/test_live_trader_orders_integration.py))
    - [x] 통합: 부분체결 2회 집계 평균가/수량/수수료 정확성
    - [x] 통합: 재시도 성공 시 단일 체결 보장(newClientOrderId 동일성)
- [x] 문서 업데이트: `README.md`에 실거래/시뮬레이션 모드 설명과 주의 사항 추가
    - [x] TESTNET 우선 검증 플로우, 보호 장치 설명, 실행 예시 및 경고 문구

## 5) 복합 전략(Composite Signal + Kelly Sizing)

- [x] 설계 확정 및 파라미터 기본값 정의(가중치, 임계치, 기간, MaxScore)
- [x] TDD: 실패 테스트 작성 및 잠금(.cursorignore 유지)
    - [x] [tests/test_composite_strategy.py](mdc:tests/test_composite_strategy.py): 각 F_i ∈ [-1,1], S 클리핑, 임계치 교차 시 BUY/SELL/HOLD, `dropna()` 후 폐봉만 사용
    - [x] [tests/test_position_sizer.py](mdc:tests/test_position_sizer.py): Kelly 계산식/클램프 검증, 점수↑ → 포지션 단조 증가
    - [x] [tests/test_risk_manager.py](mdc:tests/test_risk_manager.py): ATR·k_sl·rr로 브래킷(SL/TP) 정확성(롱/숏 대칭)
    - [x] [tests/test_live_trader_composite.py](mdc:tests/test_live_trader_composite.py): 전략 점수→사이징→브래킷→주문 플로우(모킹) 통합 검증
- [x] 전략/사이징/리스크 모듈 구현
    - [x] [strategies/composite_signal_strategy.py](mdc:strategies/composite_signal_strategy.py): EMA/BB/RSI/MACD/Volume/OBV로 점수 S 계산, `score()`/`get_signal()` 구현(순수, 외부 상태 불변)
    - [x] [strategy_factory.py](mdc:strategy_factory.py): "composite_signal" 등록 및 기본 설정 주입
    - [x] [trader/position_sizer.py](mdc:trader/position_sizer.py): `kelly_position_size(capital, win_rate, avg_win, avg_loss, score, max_score, clamps)` 추가
    - [x] [trader/risk_manager.py](mdc:trader/risk_manager.py) 신규: `compute_initial_bracket(entry, atr, side, k_sl, rr)` 구현
    - [x] [live_trader_gpt.py](mdc:live_trader_gpt.py): 점수 산출→Kelly×Confidence로 수량 결정→ATR 기반 브래킷 계산→주문 전달 연결
- [x] [trader/symbol_rules.py](mdc:trader/symbol_rules.py): 심볼별 가중치/임계치/기간 오버라이드(선택)
    - [x] `resolve_composite_params(symbol, interval, defaults)` 추가 및 `COMPOSITE_PARAM_OVERRIDES` 지원
    - [x] `live_trader_gpt.py`에서 `EXECUTION_TIMEFRAME` 기준 오버라이드 적용
- [ ] 백테스트/검증
    - [x] 폐봉 기준 루프(df[:i+1])로 룩어헤드 방지, 수수료/슬리피지 반영 (stub 구현)
    - [x] `backtest_logs/` 기록(stub): `summary.json`/`equity.csv`/`trades.csv` 생성 ([backtests/composite_backtest.py](mdc:backtests/composite_backtest.py))
    - [x] 성과지표 집계(p, b, 평균손익)로 Kelly 입력값 갱신 (요약 파일에 반영)
- [ ] 로깅/관찰성
    - [x] 점수 S, Kelly f*, Confidence, 최종 Pos, ATR, SL/TP를 체결 로그에 포함 (BUY 알림)
    - [x] 파일 기반 주문/체결/트레이드 로깅: 라이브 `live_logs/<run_id>/orders.csv,fills.csv,trades.csv,events.log` ([trader/trade_logger.py](mdc:trader/trade_logger.py), [trader/trade_executor.py](mdc:trader/trade_executor.py), [live_trader_gpt.py](mdc:live_trader_gpt.py))
- [ ] 문서/런북
    - [x] [README.md](mdc:README.md) 갱신: 전략 개요/파라미터/사용 방법
    - [x] 실행 예시 및 보호장치 주의사항 추가
    - [x] [README_ko.md](mdc:README_ko.md) 추가: 한국어 README 생성

## 6) 파일 기반 로깅 및 백테스트 산출물

- [x] 공용 로거 추가: [trader/trade_logger.py](mdc:trader/trade_logger.py)
- [x] 실거래 통합: [trader/trade_executor.py](mdc:trader/trade_executor.py)에서 SIMULATED/LIVE 공통 주문/체결/트레이드 기록
- [x] 트레이더 연결: [live_trader_gpt.py](mdc:live_trader_gpt.py)에서 `TradeLogger` 생성/주입 및 시작/종료 이벤트 기록 (`LIVE_LOG_DIR`, `RUN_ID` 지원)
- [x] 백테스트 출력: [backtests/composite_backtest.py](mdc:backtests/composite_backtest.py) `run_backtest(..., write_logs=True, log_dir, run_id)` 지원으로 `summary.json`/`equity.csv`/`trades.csv` 생성
- [x] 테스트 추가: [tests/test_trade_logger.py](mdc:tests/test_trade_logger.py), [tests/test_trade_executor_logging.py](mdc:tests/test_trade_executor_logging.py), [tests/test_backtest_logging.py](mdc:tests/test_backtest_logging.py)
- [x] 문서화: `README.md`에 로그 파일 스키마/경로, 환경변수(`LIVE_LOG_DIR`, `RUN_ID`), 백테스트 산출물 설명 추가
