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

- [ ] 레거시/손상 테스트 정리
    - [ ] 삭제된 모듈 참조(`backtester.py`, `main.py`, `strategy.py`, `position_sizer.py`, `live_trader.py`) 테스트 폐기 또는 `_archive/tests`로 이동
    - [ ] 손상된 `tests/test_backtester.py` 정리(보관 또는 삭제)
- [ ] 신규 단위 테스트 작성/수정
    - [ ] `tests/test_binance_data.py`: `get_and_update_klines`와 타입/컬럼 보장 검증(Mock 클라이언트)
    - [ ] `tests/test_state_manager.py`: 심볼별 `get_position/upsert_position` 추가 검증
    - [ ] `tests/test_strategy.py`: ATR 전략 신호/컬럼 케이스 검증
    - [ ] `tests/test_live_trader.py`: Binance `Client` 모킹 후 엔트리/청산 플로우 검증

## 3) 품질/구조/CI (Day 3)

- [ ] `pyproject.toml` 품질 도구 설정
    - [ ] Ruff/pytest 설정 추가 및 dev-deps 정리
    - [ ] 스크립트 추가: `lint`, `test`, `run-trader`
- [ ] CI 파이프라인
    - [ ] GitHub Actions 워크플로우: ruff + pytest
- [ ] 문서/환경
    - [ ] `README.md` 업데이트: 아키텍처/환경 변수/실행 방법
    - [ ] `.env.sample` 배포

## 주석
- 컬럼 네이밍은 `Open/High/Low/Close/Volume`(Title case)로 표준화합니다.
- 전략은 신호만 판정하고, 포지션 CRUD는 트레이더/상태관리자가 담당합니다.
