import logging
from typing import Dict

from binance.client import Client

from models import Position
from state_manager import StateManager


class TradeExecutor:
    def __init__(self, client: Client, data_provider, state_manager: StateManager, notifier):
        self.client = client
        self.data_provider = data_provider
        self.state_manager = state_manager
        self.notifier = notifier

    def get_usdt_balance(self) -> float:
        try:
            info = self.client.get_account()
            for bal in info.get("balances", []):
                if bal.get("asset") == "USDT":
                    return float(bal.get("free"))
        except Exception:
            return 0.0
        return 0.0

    def market_buy(self, symbol: str, usdt_to_spend: float, positions: Dict[str, Position], atr_multiplier: float, timeframe: str) -> None:
        try:
            price = self.data_provider.get_current_price(symbol)
            if price <= 0:
                return
            qty = usdt_to_spend / price
            df = self.data_provider.get_and_update_klines(symbol, timeframe)
            latest_close = float(df["Close"].iloc[-1])
            atr = float(df["atr"].iloc[-1]) if "atr" in df.columns else latest_close * 0.02
            stop_price = float(max(0.0, latest_close - atr * atr_multiplier))
            position = Position(symbol=symbol, qty=qty, entry_price=latest_close, stop_price=stop_price)
            positions[symbol] = position
            self.state_manager.save_positions(positions)
            self.notifier.send(
                f"✅ BUY {symbol} @ ${position.entry_price:.4f}\nQty: {qty:.6f}\nStop: ${position.stop_price:.4f}"
            )
        except Exception as exc:
            logging.exception(f"Failed to place BUY order for {symbol}: {exc}")
            self.notifier.send(f"❌ BUY FAILED for {symbol}: {exc}")

    def market_sell(self, symbol: str, positions: Dict[str, Position]) -> None:
        position = positions.get(symbol)
        if not position:
            return
        try:
            price = self.data_provider.get_current_price(symbol)
            del positions[symbol]
            self.state_manager.save_positions(positions)
            pnl = (price - position.entry_price) * position.qty
            self.notifier.send(f"🛑 SELL {symbol} @ ${price:.4f}\nPnL: ${pnl:.2f}")
        except Exception as exc:
            logging.exception(f"Failed to place SELL order for {symbol}: {exc}")
            self.notifier.send(f"❌ SELL FAILED for {symbol}: {exc}")


