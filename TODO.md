# 자동 거래 시스템 안정화 리팩토링 계획 (TODO)

본 계획은 3단계(런타임 안정화 → 테스트 정리 → 품질/CI)로 진행합니다. 현재 코드 구조와 일치하도록 파일명을 최신화했습니다.


## 주석
- 컬럼 네이밍은 `Open/High/Low/Close/Volume`(Title case)로 표준화합니다.
- 전략은 신호만 판정하고, 포지션 CRUD는 트레이더/상태관리자가 담당합니다.

## 4) 실거래 주문 실행 (Enable Live Orders)

- [ ] 통합 테스트: `Client.create_order` 모킹으로 엔트리/청산 플로우 검증, 규칙 위반 케이스 포함

## 5) 복합 전략(Composite Signal + Kelly Sizing)

- [ ] 백테스트/검증
- [ ] 로깅/관찰성
- [ ] 문서/런북


## 11) 코드 품질 및 구조 개선 (Code Quality & Architecture Refactoring)

### 11.1) `live_trader_gpt.py` 모듈화 및 복잡성 해소
- [x] **중간 우선순위**: 에러 처리 패턴 통일
    - [x] 일관된 에러 처리 패턴 적용 (core/error_handler.py 구현)
    - [x] 구체적인 예외 유형별 처리 로직 개선 (TradingError 하위 클래스 활용)

- [ ] **낮은 우선순위**: 코드 문서화 개선
    - [ ] 복잡한 로직들에 대한 docstring 추가
    - [ ] 메서드별 파라미터 및 반환값 명확화
    - [ ] 아키텍처 의사결정 문서화

### 11.2) Signal 및 Position 모델 개선
- [x] **중간 우선순위**: Position 클래스의 책임 분산
    - [x] 너무 많은 책임을 가진 `Position` 클래스를 분리 (PositionCalculator, PositionStateManager, PositionService)
    - [x] `PositionLeg`와 `Position`의 관계 개선 (독립적인 데이터 클래스 활용)
    - [x] 계산 로직들을 별도 서비스 클래스로 분리 (PositionCalculator)

### 11.4) 의존성 주입 및 테스트 용이성 개선
- [x] **중간 우선순위**: 의존성 주입 패턴 개선
    - [x] `ATRTrailingStopStrategy`의 생성자 의존성 간소화 (StrategyFactory 개선)
    - [x] Factory 패턴을 활용한 객체 생성 중앙화 (improved_strategy_factory.py)
    - [x] 테스트 더블의 일관성 향상 (DependencyContainer)

- [ ] **낮은 우선순위**: 테스트 코드 품질 향상
    - [ ] 테스트 데이터 팩토리 활용
    - [ ] 모킹 전략의 일관성 개선
    - [ ] 통합 테스트 커버리지 확대

### 11.5) 데이터 검증 및 타입 안정성
- [x] **중간 우선순위**: 입력 데이터 검증 강화
    - [x] `binance_data.py`의 데이터 검증 로직 개선 (binance_data_improved.py)
    - [x] Pydantic 모델을 활용한 데이터 검증 (core/data_models.py)
    - [x] API 응답 데이터의 타입 안정성 보장 (강력한 타입 검증)

- [ ] **낮은 우선순위**: 타입 힌트 완성도 향상
    - [ ] 누락된 타입 힌트 추가
    - [ ] 복잡한 타입 표현식 개선
    - [ ] mypy를 활용한 정적 타입 검사 도입

## 12) 티커별 시계열 데이터를 활용한 전략별 백테스트 시스템

### 현재 상황 분석
- **데이터**: `data/` 폴더에 5개 티커(BTCUSDT, ETHUSDT, BNBUSDT, SOLUSDT, XRPUSDT)의 5분봉 CSV 파일들이 준비되어 있음
- **전략**: `strategies/` 폴더에 ATRTrailingStopStrategy, CompositeSignalStrategy 등 3개의 전략이 구현되어 있음
- **기존 백테스트**: `backtests/composite_backtest.py`에 기본 기능이 있지만 단일 심볼/단일 전략만 지원
- **부족한 기능**: 여러 티커와 여러 전략에 대해 자동으로 백테스트를 실행하는 통합 시스템

### 구현 목표
data/ 폴더의 티커별 데이터를 활용해 여러 전략에 대해 자동으로 백테스트를 실행하고 결과를 비교할 수 있는 시스템 구축

### 12.1) 데이터 로더 시스템 구현
**목표**: data/ 폴더의 CSV 파일들을 자동으로 로드하고 전처리

**구현할 파일들**:
- [ ] `backtests/data_loader.py`: CSV 파일 자동 로드 및 전처리
- [ ] `backtests/data_manager.py`: 여러 티커 데이터 통합 관리

**주요 기능**:
- [ ] data/ 폴더 스캔하여 모든 CSV 파일 자동 발견
- [ ] 데이터 형식 검증 및 정규화
- [ ] 인디케이터 계산 (ATR, RSI 등)
- [ ] 데이터 분할 (train/validation/test)

**TDD 계획**:
- [ ] 실패 테스트 작성: CSV 파일 로드, 데이터 검증, 인디케이터 계산
- [ ] 최소 구현: 기본 파일 로드 및 검증
- [ ] 리팩토링: 성능 최적화 및 에러 처리

### 12.2) 전략 팩토리 및 설정 시스템
**목표**: 다양한 전략들을 쉽게 생성하고 파라미터를 관리

**구현할 파일들**:
- [ ] `backtests/strategy_factory.py`: 전략 생성 및 파라미터 관리
- [ ] `backtests/config_manager.py`: 백테스트 설정 관리
- [ ] `backtests/strategy_config.json`: 전략별 기본 파라미터 설정

**주요 기능**:
- [ ] ATRTrailingStopStrategy, CompositeSignalStrategy 등 전략 자동 생성
- [ ] 그리드 서치 파라미터 설정
- [ ] 전략별 최적 파라미터 관리

**TDD 계획**:
- [ ] 실패 테스트 작성: 전략 생성, 파라미터 검증
- [ ] 최소 구현: 기본 전략 팩토리
- [ ] 리팩토링: 설정 파일 통합

### 12.3) 멀티 심볼 백테스터 엔진
**목표**: 여러 티커와 여러 전략에 대해 동시에 백테스트 실행

**구현할 파일들**:
- [ ] `backtests/multi_symbol_backtester.py`: 메인 백테스트 엔진
- [ ] `backtests/backtest_runner.py`: 백테스트 실행 및 모니터링
- [ ] `backtests/parallel_executor.py`: 병렬 백테스트 실행

**주요 기능**:
- [ ] 여러 티커에 대한 동시 백테스트
- [ ] 여러 전략에 대한 동시 실행
- [ ] 실시간 진행률 모니터링
- [ ] 중간 결과 저장 및 복원

**TDD 계획**:
- [ ] 실패 테스트 작성: 멀티 심볼 실행, 결과 수집
- [ ] 최소 구현: 기본 백테스트 엔진
- [ ] 리팩토링: 병렬 처리 및 모니터링

### 12.4) 결과 관리 및 분석 시스템
**목표**: 백테스트 결과를 저장하고 비교 분석

**구현할 파일들**:
- [ ] `backtests/results_manager.py`: 결과 저장 및 로드
- [ ] `backtests/performance_analyzer.py`: 성과 지표 계산
- [ ] `backtests/results_visualizer.py`: 결과 시각화

**주요 기능**:
- [ ] 백테스트 결과 데이터베이스
- [ ] 성과 지표 자동 계산 (Sharpe ratio, MDD, Win rate 등)
- [ ] 결과 비교 및 랭킹
- [ ] 차트 및 리포트 생성

**TDD 계획**:
- [ ] 실패 테스트 작성: 결과 저장, 지표 계산
- [ ] 최소 구현: 기본 결과 관리
- [ ] 리팩토링: 시각화 및 고급 분석

### 12.5) 설정 및 실행 인터페이스
**목표**: 사용하기 쉬운 설정 파일과 실행 스크립트

**구현할 파일들**:
- [ ] `backtests/run_multi_backtest.py`: 메인 실행 스크립트
- [ ] `backtests/backtest_config.yaml`: 사용자 설정 파일
- [ ] `backtests/generate_report.py`: 리포트 생성 스크립트

**주요 기능**:
- [ ] YAML 설정 파일로 백테스트 조건 지정
- [ ] 배치 실행 스크립트
- [ ] 자동 리포트 생성

**TDD 계획**:
- [ ] 실패 테스트 작성: 설정 파일 파싱, 스크립트 실행
- [ ] 최소 구현: 기본 실행 스크립트
- [ ] 리팩토링: 사용자 인터페이스 개선

### 12.6) 통합 및 테스트
**목표**: 전체 시스템 통합 및 테스트

**구현할 파일들**:
- [ ] `tests/test_multi_backtester.py`: 통합 테스트
- [ ] `tests/test_data_loader.py`: 데이터 로더 테스트
- [ ] `tests/test_strategy_factory.py`: 전략 팩토리 테스트

**주요 기능**:
- [ ] 단위 테스트 및 통합 테스트
- [ ] 성능 벤치마크
- [ ] 예외 처리 및 로깅

**TDD 계획**:
- [ ] 실패 테스트 작성: 전체 시스템 통합
- [ ] 최소 구현: 기본 테스트 스크립트
- [ ] 리팩토링: CI/CD 파이프라인 연동

### 예상 파일 구조
```
backtests/
├── __init__.py
├── data_loader.py              # 데이터 로드 및 전처리
├── data_manager.py             # 데이터 통합 관리
├── strategy_factory.py         # 전략 생성 및 관리
├── config_manager.py           # 설정 관리
├── multi_symbol_backtester.py  # 메인 백테스트 엔진
├── backtest_runner.py          # 실행 및 모니터링
├── parallel_executor.py        # 병렬 실행
├── results_manager.py          # 결과 관리
├── performance_analyzer.py     # 성과 분석
├── results_visualizer.py       # 결과 시각화
├── run_multi_backtest.py       # 메인 실행 스크립트
└── configs/
    ├── strategy_config.json    # 전략별 파라미터
    └── backtest_config.yaml    # 사용자 설정
```

### 구현 우선순위
1. **Phase 1**: 데이터 로더 및 기본 백테스터 (1-2일)
2. **Phase 2**: 전략 팩토리 및 설정 시스템 (1-2일)
3. **Phase 3**: 멀티 심볼 백테스터 엔진 (2-3일)
4. **Phase 4**: 결과 관리 및 분석 시스템 (2-3일)
5. **Phase 5**: 통합 및 테스트 (1-2일)

### TDD 접근법
- 각 단계마다 먼저 실패하는 테스트 작성
- 최소 구현으로 테스트 통과
- 리팩토링 단계에서 코드 구조 개선
- 기존 기능의 호환성 지속 보장
- .cursorignore에 테스트 잠금 규칙 적용