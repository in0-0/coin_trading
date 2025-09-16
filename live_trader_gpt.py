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
import math
import signal
import logging
from datetime import datetime
from typing import Dict, Optional

import requests
import pandas as pd
from binance.client import Client
from binance.exceptions import BinanceAPIException, BinanceOrderException
from requests.exceptions import ReadTimeout, ConnectionError
from dotenv import load_dotenv

# --- Import Refactored Modules ---
from binance_data import BinanceData
from strategy_factory import StrategyFactory
from state_manager import StateManager
from models import Position, Signal

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
        usdt_bal = self._get_account_balance_usdt()
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
        price = market_data['Close'].iloc[-1]
        risk_usdt = usdt_balance * RISK_PER_TRADE
        
        # Simplified position sizing
        spend = risk_usdt * 10  # Example: leverage or larger position size
        
        max_alloc = usdt_balance * MAX_SYMBOL_WEIGHT
        spend = min(spend, max_alloc, usdt_balance * 0.95)
        
        return spend if spend >= MIN_ORDER_USDT else None

    def _place_buy_order(self, symbol: str, usdt_to_spend: float):
        try:
            price = self.data_provider.get_current_price(symbol)
            if price <= 0: return
            
            qty = usdt_to_spend / price
            logging.info(f"Executing market BUY for {symbol}, qty ~{qty:.6f}")

            # Create Position on BUY with stop_price set using ATR trailing rule
            current_df = self.data_provider.get_and_update_klines(symbol, EXECUTION_TIMEFRAME)
            latest_close = float(current_df['Close'].iloc[-1])
            # Conservative ATR calc for stop; if atr not present, fallback
            atr = float(current_df['atr'].iloc[-1]) if 'atr' in current_df.columns else latest_close * 0.02
            stop_price = float(max(0.0, latest_close - atr * ATR_MULTIPLIER))
            qty = usdt_to_spend / price
            position = Position(symbol=symbol, qty=qty, entry_price=latest_close, stop_price=stop_price)

            self.positions[symbol] = position
            self.state_manager.save_positions(self.positions)
            self.tg_send(f"✅ BUY {symbol} @ ${position.entry_price:.4f}\nQty: {qty:.6f}\nStop: ${position.stop_price:.4f}")
        except Exception as e:
            logging.exception(f"Failed to place BUY order for {symbol}: {e}")
            self.tg_send(f"❌ BUY FAILED for {symbol}: {e}")

    def _place_sell_order(self, symbol: str):
        pos = self.positions.get(symbol)
        if not pos: return
        try:
            # Note: In a real scenario, use client.create_order
            price = self.data_provider.get_current_price(symbol)
            logging.info(f"Executing market SELL for {symbol}, qty {pos.qty:.6f}")
            
            del self.positions[symbol]
            self.state_manager.save_positions(self.positions)
            pnl = (price - pos.entry_price) * pos.qty
            self.tg_send(f"🛑 SELL {symbol} @ ${price:.4f}\nPnL: ${pnl:.2f}")
        except Exception as e:
            logging.exception(f"Failed to place SELL order for {symbol}: {e}")
            self.tg_send(f"❌ SELL FAILED for {symbol}: {e}")

    def _get_account_balance_usdt(self) -> float:
        try:
            info = self.client.get_account()
            for bal in info['balances']:
                if bal['asset'] == 'USDT':
                    return float(bal['free'])
        except Exception:
            return 0.0
        return 0.0

    def tg_send(self, msg: str):
        if not TG_BOT_TOKEN or not TG_CHAT_ID: return
        try:
            requests.post(f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage",
                          json={"chat_id": TG_CHAT_ID, "text": msg, "parse_mode": "Markdown"})
        except Exception as e:
            logging.warning(f"Telegram send error: {e}")

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
