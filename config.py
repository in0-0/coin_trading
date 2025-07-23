#-*- coding: utf-8 -*-
from binance.client import Client

"""전략 및 거래 설정을 관리하는 파일"""

BACKTEST_SETTINGS = {
    "initial_capital": 10000
}

TRADE_SETTINGS = {
    "symbol": "BTCUSDT",
    "interval": Client.KLINE_INTERVAL_4HOUR,
    "start_date": "1 year ago UTC"
}

STRATEGY_CONFIG = {
    "ma_cross": {
        "params": {"short_window": 10, "long_window": 30},
        "exit_params": {},
        "description": "이동평균선 교차 시 진입/청산 신호를 모두 생성합니다."
    },
    "buy_hold": {
        "params": {},
        "exit_params": {},
        "description": "단순 매수 후 보유합니다."
    },
    "vol_momentum": {
        "params": {"k": 0.5, "rsi_period": 14, "rsi_threshold": 50},
        "exit_params": {"stop_loss_pct": 0.02, "time_cut_period": 6},
        "description": "변동성 돌파 시 진입, 2% 손절 또는 24시간(4h*6) 후 청산합니다."
    },
    "ma_reversion": {
        "params": {"ma_period": 20, "reversion_pct": 0.05},
        "exit_params": {"take_profit_pct": 0.03, "stop_loss_pct": 0.07, "reaches_ma": True},
        "description": "이평선 과대 낙폭 시 진입, 3% 익절, 7% 손절, 또는 이평선 도달 시 청산합니다."
    }
}