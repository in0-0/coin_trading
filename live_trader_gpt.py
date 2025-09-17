#!/usr/bin/env python3
"""
live_trader_refactored.py

A refactored spot auto-trader that integrates modularized components for
data handling, strategy execution, and state management.

Key Improvements:
- Modular Architecture: Separates concerns into DataProvider, Strategy, and StateManager.
- No Repainting: Signal and ATR calculations are based on closed candles to prevent lookahead bias.
- Persistent State: Saves and loads trading positions to/from a file, ensuring resilience.
- Efficient Data Handling: Fetches only new data since the last update, reducing API calls.
"""

import os
import time
import signal
import logging
from typing import Dict, Optional

import requests
import pandas as pd
from binance.client import Client
from dotenv import load_dotenv

# --- Import Refactored Modules ---
from binance_data import BinanceData
from strategy_factory import StrategyFactory
from state_manager import StateManager
from models import Position, Signal
from trader import Notifier, PositionSizer, TradeExecutor

load_dotenv()

# ------------------ Configuration ------------------
SYMBOLS = os.getenv("SYMBOLS", "BTCUSDT,ETHUSDT,BNBUSDT,SOLUSDT,XRPUSDT").split(",")
EXEC_INTERVAL = int(os.getenv("EXEC_INTERVAL_SECONDS", "60"))
TIMEFRAMES = {"1h": "1h", "4h": "4h", "15m": "15m", "5m": "5m"}
TF_WEIGHTS = {"4h": 0.35, "1h": 0.25, "15m": 0.18, "5m": 0.12}
STRAT_WEIGHTS = {"ema": 0.266, "rsi": 0.156, "bb": 0.577}
ENTER_THRESHOLD = 0.6
EXECUTION_TIMEFRAME = '5m'

ATR_PERIOD = 14
ATR_MULTIPLIER = 0.5
RISK_PER_TRADE = 0.005

MAX_CONCURRENT_POS = 3
MAX_SYMBOL_WEIGHT = 0.20
MIN_ORDER_USDT = 10.0

LOG_FILE = os.getenv("LOG_FILE", "live_trader.log")
TG_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s",
                    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()])

# ------------------ LiveTrader Class ------------------

class LiveTrader:
    def __init__(self):
        self._running = True
        self._setup_client()
        self.data_provider = BinanceData(self.api_key, self.api_secret)
        self.state_manager = StateManager("live_positions.json")
        self.notifier = Notifier(TG_BOT_TOKEN, TG_CHAT_ID)
        self.position_sizer = PositionSizer(
            risk_per_trade=RISK_PER_TRADE,
            max_symbol_weight=MAX_SYMBOL_WEIGHT,
            min_order_usdt=MIN_ORDER_USDT,
        )
        self.executor = TradeExecutor(self.client, self.data_provider, self.state_manager, self.notifier)
        self.strategies = {
            symbol: self._setup_strategy(symbol) for symbol in SYMBOLS
        }
        self.positions: Dict[str, Position] = self.state_manager.load_positions()
        logging.info(f"Loaded {len(self.positions)} positions from state file.")

    def _setup_client(self):
        self.mode = os.getenv("MODE", "TESTNET").upper()
        if self.mode not in ("TESTNET", "REAL"):
            raise SystemExit("MODE must be TESTNET or REAL")

        if self.mode == "TESTNET":
            self.api_key = os.getenv("TESTNET_BINANCE_API_KEY")
            self.api_secret = os.getenv("TESTNET_BINANCE_SECRET_KEY")
        else:
            self.api_key = os.getenv("BINANCE_API_KEY")
            self.api_secret = os.getenv("BINANCE_SECRET_KEY")

        if not self.api_key or not self.api_secret:
            logging.warning("API keys not set. Real orders cannot be placed.")
        
        self.client = Client(self.api_key, self.api_secret, testnet=(self.mode == "TESTNET"))
        if self.mode == "TESTNET":
            self.client.API_URL = 'https://testnet.binance.vision/api'
        logging.info(f"Using Binance {self.mode}")

    def _setup_strategy(self, symbol: str):
        factory = StrategyFactory()
        return factory.create_strategy(
            "atr_trailing_stop",
            symbol=symbol,
            atr_multiplier=ATR_MULTIPLIER,
            risk_per_trade=RISK_PER_TRADE,
        )

    def run(self):
        self.tg_send(f"Trader started in {self.mode} mode. Symbols: {', '.join(SYMBOLS)}")
        while self._running:
            try:
                self._check_stops()
                self._find_and_execute_entries()
                time.sleep(EXEC_INTERVAL)
            except Exception as e:
                logging.exception("Main loop error: %s", e)
                self.tg_send(f"Main loop error: {e}")
                time.sleep(5)
        self._shutdown()

    def _check_stops(self):
        for sym, pos in list(self.positions.items()):
            try:
                price = self.data_provider.get_current_price(sym)
                if price > 0 and price <= pos.stop_price:
                    logging.info(f"Stop triggered for {sym} at price={price}, stop={pos.stop_price}")
                    self._place_sell_order(sym)
            except Exception as e:
                logging.exception(f"Error checking stop for {sym}: {e}")

    def _find_and_execute_entries(self):
        usdt_bal = self.executor.get_usdt_balance()
        if usdt_bal <= MIN_ORDER_USDT:
            return

        concurrent = len(self.positions)
        for sym in SYMBOLS:
            if sym in self.positions or concurrent >= MAX_CONCURRENT_POS:
                continue

            strategy = self.strategies[sym]
            market_data = self.data_provider.get_and_update_klines(sym, EXECUTION_TIMEFRAME)
            signal = strategy.get_signal(market_data, self.positions.get(sym))
            logging.info(f"Signal for {sym}: {signal}")

            if signal == Signal.BUY:
                spend_amount = self._calculate_position_size(sym, usdt_bal, market_data)
                if spend_amount:
                    self._place_buy_order(sym, spend_amount)
                    concurrent += 1
            elif signal == Signal.SELL:
                self._place_sell_order(sym)

    

    def _calculate_position_size(self, symbol: str, usdt_balance: float, market_data: pd.DataFrame) -> Optional[float]:
        return self.position_sizer.compute_spend_amount(usdt_balance, market_data)

    def _place_buy_order(self, symbol: str, usdt_to_spend: float):
        # Delegate to executor which manages position persistence and notifications
        self.executor.market_buy(
            symbol=symbol,
            usdt_to_spend=usdt_to_spend,
            positions=self.positions,
            atr_multiplier=ATR_MULTIPLIER,
            timeframe=EXECUTION_TIMEFRAME,
        )

    def _place_sell_order(self, symbol: str):
        self.executor.market_sell(symbol, self.positions)

    def _get_account_balance_usdt(self) -> float:
        return self.executor.get_usdt_balance()

    def tg_send(self, msg: str):
        self.notifier.send(msg)

    def stop(self):
        self._running = False

    def _shutdown(self):
        logging.info("Shutdown initiated. Closing all positions...")
        for sym in list(self.positions.keys()):
            self._place_sell_order(sym)
        self.tg_send("🤖 Trader stopped. All positions closed.")
        logging.info("Exited main loop.")

# ------------------ Main Execution ------------------
_trader_instance = None

def shutdown_handler(signum, frame):
    logging.warning("Termination signal received. Shutting down...")
    if _trader_instance:
        _trader_instance.stop()

if __name__ == "__main__":
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)
    
    try:
        _trader_instance = LiveTrader()
        _trader_instance.run()
    except Exception as e:
        logging.exception("A fatal error occurred in the trader.")
        if TG_BOT_TOKEN:
            requests.post(f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage",
                          json={"chat_id": TG_CHAT_ID, "text": f"🔥 FATAL ERROR: {e}"})
        raise
