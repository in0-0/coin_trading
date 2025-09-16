# 자동 거래 시스템 안정화 리팩토링 계획 (TODO)

## 1. 데이터 계층: 증분 업데이트 및 영속성 구축

- [ ] **`data_provider.py` 모듈 생성 또는 `binance_data.py` 확장:**
    - [ ] `get_klines(symbol, timeframe)` 함수 구현:
        - [ ] **로컬 데이터 확인:** `data/{symbol}_{timeframe}.csv` 파일 존재 여부 확인.
        - [ ] **증분 업데이트:** 파일이 있으면 마지막 타임스탬프를 읽어와, 그 이후의 최신 캔들 데이터만 API로 요청 (`startTime` 파라미터 활용).
        - [ ] **초기 데이터 로드:** 파일이 없으면, 보조지표 계산에 충분한 과거 데이터(e.g., 1000개)를 다운로드하여 새 CSV 파일 생성.
        - [ ] **데이터 병합 및 저장:** 새로 받은 데이터를 기존 데이터와 병합하고 중복 제거 후 전체를 다시 CSV에 저장.
        - [ ] **DataFrame 반환:** 항상 최신 데이터가 포함된 전체 Pandas DataFrame을 반환.

## 2. 전략 계층: "Repainting" 없는 신호 계산

- [ ] **`strategy.py` 모듈 리팩토링:**
    - [ ] `calculate_aggregate_signal(df_dict)` 함수 재설계:
        - [ ] 입력값으로 각 타임프레임별 DataFrame을 담은 딕셔너리(`{'1h': df_1h, '4h': df_4h, ...}`)를 받도록 수정.
        - [ ] **마감된 캔들 기준 계산:** 모든 보조지표(EMA, RSI, BB) 계산 시, `df.iloc[-2]`를 사용하여 가장 최근에 '마감된' 캔들 데이터를 사용하도록 로직 수정.
        - [ ] 최종 가중 점수를 계산하여 반환.

## 3. 상태 관리 계층: 포지션 정보 영속화

- [ ] **`state_manager.py` 모듈 활용:**
    - [ ] `save_positions(positions: dict)` 함수 구현:
        - [ ] 현재 `positions` 딕셔너리를 `live_positions.json` 파일에 JSON 형식으로 저장.
    - [ ] `load_positions() -> dict` 함수 구현:
        - [ ] `live_positions.json` 파일이 존재하면, 파일 내용을 읽어와 파이썬 딕셔너리로 변환하여 반환.
        - [ ] 파일이 없으면, 빈 딕셔너리 반환.

## 4. 실행 계층: 메인 루프 리팩토링

- [ ] **`live_trader_gpt.py` (또는 `main.py`) 리팩토링:**
    - [ ] **초기화 로직:**
        - [ ] 스크립트 시작 시, `state_manager.load_positions()`를 호출하여 `positions` 딕셔너리 초기화.
    - [ ] **메인 루프 수정:**
        - [ ] **데이터 수집:** 루프 시작 시, 각 심볼과 타임프레임에 대해 `data_provider.get_klines()`를 호출하여 최신 데이터를 가져옴.
        - [ ] **신호 계산:** `strategy.calculate_aggregate_signal()`에 수집된 데이터를 전달하여 거래 점수(score) 획득.
        - [ ] **포지션 규모 계산 (ATR):**
            - [ ] `position_sizer.py` 모듈 활용 고려.
            - [ ] ATR 계산 시, 실행 타임프레임(e.g., '5m')의 '마감된' 캔들(`iloc[-2]`)을 사용하여 Repainting 방지.
        - [ ] **주문 실행 및 상태 저장:**
            - [ ] `place_market_buy` 또는 `place_market_sell_all` 함수 실행 **직후**, `state_manager.save_positions(positions)`를 즉시 호출하여 최신 상태를 파일에 저장.
    - [ ] **오류 처리 및 로깅 개선:** 각 계층(데이터, 전략, 실행)에서 발생하는 예외를 명확히 구분하여 로깅.
