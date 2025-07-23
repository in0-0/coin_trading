#-*- coding: utf-8 -*-
from binance.client import Client

"""전략 및 거래 설정을 관리하는 파일"""

# --- 백테스팅 설정 ---
BACKTEST_SETTINGS = {
    "initial_capital": 10000  # 초기 자본금 (USD)
}

# --- 거래 기본 설정 ---
TRADE_SETTINGS = {
    "symbol": "BTCUSDT",
    "interval": Client.KLINE_INTERVAL_4HOUR,
    "start_date": "1 year ago UTC" # 백테스팅 기간 설정
}

# --- 전략별 상세 설정 ---
STRATEGY_CONFIG = {
    "ma_cross": {
        "params": {"short_window": 10, "long_window": 30},
        "signal_meaning": {
            1: "매수 (단기 이평선 > 장기 이평선)",
            -1: "매도 (단기 이평선 < 장기 이평선)",
            0: "관망"
        }
    },
    "buy_hold": {
        "params": {},
        "signal_meaning": {
            1: "매수 후 보유"
        }
    },
    "vol_momentum": {
        "params": {"k": 0.5, "rsi_period": 14, "rsi_threshold": 50},
        "signal_meaning": {
            1: "매수 (변동성 돌파 & 모멘텀 확인)",
            0: "관망"
        }
    },
    "ma_reversion": {
        "params": {"ma_period": 20, "reversion_pct": 0.05},
        "signal_meaning": {
            1: "매수 (이평선 대비 과대 낙폭)",
            0: "관망"
        }
    }
}