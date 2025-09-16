# -*- coding: utf-8 -*-
import os
from binance.client import Client
from dotenv import load_dotenv

load_dotenv()

"""전략 및 거래 설정을 관리하는 파일"""

# -----------------------------------------------------------------------------
# 모드 설정 ( 'backtest' 또는 'live' )
# -----------------------------------------------------------------------------
MODE = "backtest"  # 'backtest' 또는 'live'

# -----------------------------------------------------------------------------
# API 키 설정
# -----------------------------------------------------------------------------
# 실제 거래 시 .env 파일에 BINANCE_API_KEY와 BINANCE_SECRET_KEY를 설정해야 합니다.
API_KEY = os.environ.get("BINANCE_API_KEY")
SECRET_KEY = os.environ.get("BINANCE_SECRET_KEY")

# -----------------------------------------------------------------------------
# 백테스팅 전용 설정
# -----------------------------------------------------------------------------
BACKTEST_SETTINGS = {
    "initial_capital": 10000,
    "start_date": "1 year ago UTC",
    "symbols": ["BTCUSDT", "ETHUSDT"],  # 여러 심볼 테스트 가능하도록 변경
    "interval": Client.KLINE_INTERVAL_4HOUR,
}

# -----------------------------------------------------------------------------
# 실시간 거래 전용 설정
# -----------------------------------------------------------------------------
LIVE_TRADE_SETTINGS = {
    "symbol": "BTCUSDT",
    "interval": "4h",
    "strategy_name": "vol_momentum",  # 실시간 거래에 사용할 단일 전략
    "state_file": "live_trade_state.json",
}

# -----------------------------------------------------------------------------
# 전략 상세 설정
# -----------------------------------------------------------------------------
STRATEGY_CONFIG = {
    "ma_cross": {
        "params": {"short_window": 10, "long_window": 30},
        "position_sizer": {"name": "all_in"},
        "exit_params": {},
        "description": "이동평균선 교차 시 진입/청산 신호를 모두 생성합니다.",
    },
    "buy_hold": {
        "params": {},
        "position_sizer": {"name": "all_in"},
        "exit_params": {},
        "description": "단순 매수 후 보유합니다.",
    },
    "vol_momentum": {
        "params": {"k": 0.5, "rsi_period": 14, "rsi_threshold": 50},
        "position_sizer": {
            "name": "fixed_fractional",
            "params": {"risk_fraction": 0.02},
        },
        "exit_params": {"stop_loss_pct": 0.02, "time_cut_period": 6},
        "description": "변동성 돌파 시 진입, 2% 손절 또는 24시간(4h*6) 후 청산합니다.",
    },
    "ma_reversion": {
        "params": {"ma_period": 20, "reversion_pct": 0.05},
        "position_sizer": {
            "name": "fixed_fractional",
            "params": {"risk_fraction": 0.05},
        },
        "exit_params": {
            "take_profit_pct": 0.03,
            "stop_loss_pct": 0.07,
            "reaches_ma": True,
        },
        "description": "이평선 과대 낙폭 시 진입, 3% 익절, 7% 손절, 또는 이평선 도달 시 청산합니다.",
    },
}
