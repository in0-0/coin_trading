import logging
import time
import random
from typing import Dict, Any, Optional, Tuple

from binance.client import Client

from models import Position
from .risk_manager import compute_initial_bracket
from state_manager import StateManager
from .symbol_rules import (
    get_symbol_filters,
    round_qty_to_step,
    validate_min_notional,
)
try:
    from .trade_logger import TradeLogger  # optional at runtime
except Exception:  # pragma: no cover
    TradeLogger = None  # type: ignore


class TradeExecutor:
    def __init__(
        self,
        client: Client,
        data_provider,
        state_manager: StateManager,
        notifier,
        *,
        execution_mode: str = "SIMULATED",
        max_slippage_bps: int = 50,
        order_timeout_sec: int = 10,
        order_retry: int = 3,
        kill_switch: bool = False,
        trade_logger: Optional["TradeLogger"] = None,
    ):
        self.client = client
        self.data_provider = data_provider
        self.state_manager = state_manager
        self.notifier = notifier
        # Execution configuration (stored for future LIVE integration)
        self.execution_mode = execution_mode.upper()
        self.max_slippage_bps = max_slippage_bps
        self.order_timeout_sec = order_timeout_sec
        self.order_retry = order_retry
        self.kill_switch = kill_switch
        self.trade_logger = trade_logger

    # --------------- Internal helpers ---------------
    def _generate_client_order_id(self, side: str, symbol: str) -> str:
        base = f"gptbot-{side}-{symbol.lower()}"
        suffix = f"-{int(time.time()*1000)}-{random.randint(100,999)}"
        return base + suffix

    def _with_retries_and_status_check(self, symbol: str, client_order_id: str, place_fn) -> Optional[Dict[str, Any]]:
        retries = max(0, getattr(self, "order_retry", 3))
        delay = 0.5
        for attempt in range(retries + 1):
            try:
                resp = place_fn()
                if resp:
                    return resp
            except Exception as exc:
                logging.warning("Order place attempt %d failed for %s: %s", attempt + 1, symbol, exc)
                # try to query by clientOrderId if supported
                try:
                    # Some clients may not support searching by clientOrderId directly; placeholder for actual lookup
                    orders = self.client.get_all_orders(symbol=symbol, limit=5)
                    for o in orders or []:
                        if o.get("clientOrderId") == client_order_id:
                            return o
                except Exception:
                    pass
            time.sleep(delay + random.random() * 0.2)
            delay = min(2.0, delay * 1.5)
        return None

    def _compute_fills(self, resp: Dict[str, Any]) -> Tuple[float, float, float, Optional[str]]:
        fills = resp.get("fills") or []
        if not fills:
            # Some endpoints return cummulative fields
            executed_qty = float(resp.get("executedQty", 0.0))
            cummulative_quote = float(resp.get("cummulativeQuoteQty", 0.0))
            avg_price = (cummulative_quote / executed_qty) if executed_qty > 0 else 0.0
            # Fee info may not be available; return zeros
            return avg_price, executed_qty, 0.0, None
        total_quote = 0.0
        total_base = 0.0
        total_fee = 0.0
        fee_asset = None
        for f in fills:
            price = float(f.get("price", 0.0))
            qty = float(f.get("qty", 0.0))
            fee = float(f.get("commission", 0.0))
            fee_asset = f.get("commissionAsset", fee_asset)
            total_quote += price * qty
            total_base += qty
            total_fee += fee
        avg_price = (total_quote / total_base) if total_base > 0 else 0.0
        return avg_price, total_base, total_fee, fee_asset

    def _is_slippage_within_limit(self, symbol: str) -> bool:
        max_bps = max(0, getattr(self, "max_slippage_bps", 0))
        if max_bps <= 0:
            return True
        try:
            tick = self.client.get_orderbook_ticker(symbol=symbol)
            bid = float(tick.get("bidPrice", 0.0))
            ask = float(tick.get("askPrice", 0.0))
            if bid <= 0 or ask <= 0:
                return True
            mid = (bid + ask) / 2.0
            spread_bps = (ask - bid) / mid * 10000.0
            return spread_bps <= max_bps
        except Exception:
            return True

    def _poll_order_until_done(self, symbol: str, initial_resp: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            order_id = initial_resp.get("orderId")
            client_order_id = initial_resp.get("clientOrderId") or initial_resp.get("origClientOrderId")
            timeout_sec = max(1, getattr(self, "order_timeout_sec", 10))
            deadline = time.time() + timeout_sec
            last = initial_resp
            while time.time() < deadline:
                try:
                    if order_id:
                        last = self.client.get_order(symbol=symbol, orderId=order_id)
                    elif client_order_id:
                        last = self.client.get_order(symbol=symbol, origClientOrderId=client_order_id)
                    else:
                        break
                    if str(last.get("status", "")).upper() == "FILLED":
                        return last
                except Exception:
                    pass
                time.sleep(0.5)
            return last
        except Exception:
            return None

    def get_usdt_balance(self) -> float:
        try:
            info = self.client.get_account()
            for bal in info.get("balances", []):
                if bal.get("asset") == "USDT":
                    return float(bal.get("free"))
        except Exception:
            return 0.0
        return 0.0

    def market_buy(self, symbol: str, usdt_to_spend: float, positions: Dict[str, Position], atr_multiplier: float, timeframe: str, *, k_sl: float = 1.0, rr: float = 1.5, score_meta: Optional[Dict[str, float]] = None) -> None:
        try:
            if getattr(self, "kill_switch", False) and getattr(self, "execution_mode", "SIMULATED") == "LIVE":
                self.notifier.send("⛔ Kill switch active. Skipping LIVE BUY order.")
                return

            mode = getattr(self, "execution_mode", "SIMULATED")
            if mode == "LIVE":
                if not self._is_slippage_within_limit(symbol):
                    self.notifier.send(f"⚠️ Skipping BUY {symbol}: spread exceeds MAX_SLIPPAGE_BPS")
                    return

                client_order_id = self._generate_client_order_id("buy", symbol)

                def _place() -> Dict[str, Any]:
                    return self.client.create_order(
                        symbol=symbol,
                        side="BUY",
                        type="MARKET",
                        quoteOrderQty=round(float(usdt_to_spend), 2),
                        newOrderRespType="FULL",
                        newClientOrderId=client_order_id,
                    )

                resp = self._with_retries_and_status_check(symbol, client_order_id, _place)
                if not resp:
                    self.notifier.send(f"❌ LIVE BUY FAILED {symbol}: no response")
                    return

                # If not fully filled, poll until filled or timeout
                if str(resp.get("status", "")).upper() != "FILLED":
                    polled = self._poll_order_until_done(symbol, resp)
                    if polled:
                        resp = polled
                    # Final idempotent lookup by clientOrderId to catch fills after timeout
                    if str(resp.get("status", "")).upper() != "FILLED":
                        try:
                            client_order_id = resp.get("clientOrderId") or resp.get("origClientOrderId")
                            if client_order_id:
                                orders = self.client.get_all_orders(symbol=symbol, limit=10)
                                for o in orders or []:
                                    if o.get("clientOrderId") == client_order_id and str(o.get("status", "")).upper() == "FILLED":
                                        resp = o
                                        break
                        except Exception:
                            pass

                avg_price, executed_qty, total_fee, fee_asset = self._compute_fills(resp)
                if executed_qty <= 0:
                    self.notifier.send(f"❌ LIVE BUY FAILED {symbol}: zero executed qty")
                    return

                df = self.data_provider.get_and_update_klines(symbol, timeframe)
                latest_close = float(df["Close"].iloc[-1])
                atr = float(df["atr"].iloc[-1]) if "atr" in df.columns else latest_close * 0.02
                try:
                    sl, tp = compute_initial_bracket(entry=avg_price, atr=atr, side="long", k_sl=float(k_sl), rr=float(rr))
                except Exception:
                    sl = float(max(0.0, latest_close - atr * atr_multiplier))
                    tp = float(latest_close + atr * atr_multiplier)
                # Log order/fill (LIVE)
                try:
                    if self.trade_logger is not None:
                        self.trade_logger.log_order(symbol=symbol, side="BUY", price=avg_price, qty=executed_qty, quote_qty=None, client_order_id=client_order_id)
                        self.trade_logger.log_fill(symbol=symbol, side="BUY", price=avg_price, qty=executed_qty, fee=total_fee, fee_asset=fee_asset, order_id=resp.get("orderId"), client_order_id=client_order_id)
                except Exception:
                    pass

                position = Position(symbol=symbol, qty=executed_qty, entry_price=avg_price, stop_price=float(sl))
                positions[symbol] = position
                self.state_manager.save_positions(positions)
                order_id = resp.get("orderId") or resp.get("clientOrderId") or client_order_id
                fee_msg = f" | Fee: {total_fee:.6f} {fee_asset}" if total_fee > 0 and fee_asset else ""
                meta = score_meta or {}
                s = meta.get("score")
                conf = meta.get("confidence")
                kf = meta.get("kelly_f")
                meta_parts = []
                if isinstance(s, (int, float)):
                    meta_parts.append(f"S={float(s):.3f}")
                if isinstance(conf, (int, float)):
                    meta_parts.append(f"Conf={float(conf):.2f}")
                if isinstance(kf, (int, float)):
                    meta_parts.append(f"f*={float(kf):.3f}")
                meta_str = (" " + " ".join(meta_parts)) if meta_parts else ""
                self.notifier.send(
                    f"✅ BUY {symbol} (LIVE) id={order_id}\nAvg: ${avg_price:.4f} Qty: {executed_qty:.6f}{fee_msg}\nSL: ${sl:.4f} TP: ${tp:.4f}{meta_str} ATR=${atr:.4f}"
                )
                return

            # SIMULATED branch (existing behavior)
            price = self.data_provider.get_current_price(symbol)
            if price <= 0:
                return
            qty = usdt_to_spend / price
            # Log order for SIMULATED buy
            try:
                if self.trade_logger is not None:
                    self.trade_logger.log_order(symbol=symbol, side="BUY", price=price, qty=qty, quote_qty=usdt_to_spend, client_order_id=None)
            except Exception:
                pass
            df = self.data_provider.get_and_update_klines(symbol, timeframe)
            latest_close = float(df["Close"].iloc[-1])
            atr = float(df["atr"].iloc[-1]) if "atr" in df.columns else latest_close * 0.02
            try:
                sl, tp = compute_initial_bracket(entry=latest_close, atr=atr, side="long", k_sl=float(k_sl), rr=float(rr))
            except Exception:
                sl = float(max(0.0, latest_close - atr * atr_multiplier))
                tp = float(latest_close + atr * atr_multiplier)
            position = Position(symbol=symbol, qty=qty, entry_price=latest_close, stop_price=float(sl))
            positions[symbol] = position
            self.state_manager.save_positions(positions)
            # Log simulated fill right away
            try:
                if self.trade_logger is not None:
                    self.trade_logger.log_fill(symbol=symbol, side="BUY", price=latest_close, qty=qty, fee=0.0, fee_asset=None, order_id=None, client_order_id=None)
            except Exception:
                pass
            meta = score_meta or {}
            s = meta.get("score")
            conf = meta.get("confidence")
            kf = meta.get("kelly_f")
            meta_parts = []
            if isinstance(s, (int, float)):
                meta_parts.append(f"S={float(s):.3f}")
            if isinstance(conf, (int, float)):
                meta_parts.append(f"Conf={float(conf):.2f}")
            if isinstance(kf, (int, float)):
                meta_parts.append(f"f*={float(kf):.3f}")
            meta_str = (" " + " ".join(meta_parts)) if meta_parts else ""
            self.notifier.send(
                f"✅ BUY {symbol} @ ${position.entry_price:.4f}\nQty: {qty:.6f}\nSL: ${sl:.4f} TP: ${tp:.4f}{meta_str} ATR=${atr:.4f}"
            )
        except Exception as exc:
            logging.exception(f"Failed to place BUY order for {symbol}: {exc}")
            self.notifier.send(f"❌ BUY FAILED for {symbol}: {exc}")

    def market_sell(self, symbol: str, positions: Dict[str, Position]) -> None:
        position = positions.get(symbol)
        if not position:
            return
        try:
            if getattr(self, "kill_switch", False) and getattr(self, "execution_mode", "SIMULATED") == "LIVE":
                self.notifier.send("⛔ Kill switch active. Skipping LIVE SELL order.")
                return

            mode = getattr(self, "execution_mode", "SIMULATED")
            if mode == "LIVE":
                if not self._is_slippage_within_limit(symbol):
                    self.notifier.send(f"⚠️ Skipping SELL {symbol}: spread exceeds MAX_SLIPPAGE_BPS")
                    return

                # Round to step and validate notional
                filters = get_symbol_filters(self.client, symbol, cache={})
                bid_ask = self.client.get_orderbook_ticker(symbol=symbol)
                bid = float(bid_ask.get("bidPrice", 0.0))
                qty_rounded = round_qty_to_step(float(position.qty), filters.lot_step_size)
                if qty_rounded <= 0 or qty_rounded < filters.lot_min_qty:
                    self.notifier.send(f"❌ SELL {symbol} blocked: qty below min step/minQty after rounding")
                    return
                if not validate_min_notional(bid, qty_rounded, filters.min_notional):
                    self.notifier.send(f"❌ SELL {symbol} blocked: notional below MIN_NOTIONAL")
                    return

                client_order_id = self._generate_client_order_id("sell", symbol)

                def _place() -> Dict[str, Any]:
                    return self.client.create_order(
                        symbol=symbol,
                        side="SELL",
                        type="MARKET",
                        quantity=qty_rounded,
                        newOrderRespType="FULL",
                        newClientOrderId=client_order_id,
                    )

                resp = self._with_retries_and_status_check(symbol, client_order_id, _place)
                if not resp:
                    self.notifier.send(f"❌ LIVE SELL FAILED {symbol}: no response")
                    return

                # If not fully filled, poll until filled or timeout
                if str(resp.get("status", "")).upper() != "FILLED":
                    polled = self._poll_order_until_done(symbol, resp)
                    if polled:
                        resp = polled

                avg_price, executed_qty, total_fee, fee_asset = self._compute_fills(resp)
                if executed_qty <= 0:
                    self.notifier.send(f"❌ LIVE SELL FAILED {symbol}: zero executed qty")
                    return

                # Log fill and remove position and compute PnL (approx; adjust for fee in quote if applicable)
                try:
                    if self.trade_logger is not None:
                        self.trade_logger.log_order(symbol=symbol, side="SELL", price=avg_price, qty=executed_qty, quote_qty=None, client_order_id=client_order_id)
                        self.trade_logger.log_fill(symbol=symbol, side="SELL", price=avg_price, qty=executed_qty, fee=total_fee, fee_asset=fee_asset, order_id=resp.get("orderId"), client_order_id=client_order_id)
                except Exception:
                    pass
                del positions[symbol]
                self.state_manager.save_positions(positions)
                pnl = (avg_price - position.entry_price) * min(position.qty, executed_qty)
                if fee_asset and fee_asset.upper() in symbol and fee_asset.upper() != symbol.replace("USDT", ""):
                    # If fee asset is quote (e.g., USDT), subtract from PnL
                    if fee_asset.upper() == "USDT":
                        pnl -= total_fee
                order_id = resp.get("orderId") or resp.get("clientOrderId") or client_order_id
                fee_msg = f" | Fee: {total_fee:.6f} {fee_asset}" if total_fee > 0 and fee_asset else ""
                # Log trade summary
                try:
                    if self.trade_logger is not None:
                        pnl_pct = (avg_price / position.entry_price - 1.0) if position.entry_price > 0 else 0.0
                        self.trade_logger.log_trade(symbol=symbol, entry_price=position.entry_price, exit_price=avg_price, qty=min(position.qty, executed_qty), pnl=pnl, pnl_pct=pnl_pct)
                except Exception:
                    pass
                self.notifier.send(f"🛑 SELL {symbol} (LIVE) id={order_id}\nAvg: ${avg_price:.4f} Qty: {executed_qty:.6f}{fee_msg}\nPnL: ${pnl:.2f}")
                return

            price = self.data_provider.get_current_price(symbol)
            # Log order for SIMULATED sell
            try:
                if self.trade_logger is not None:
                    self.trade_logger.log_order(symbol=symbol, side="SELL", price=price, qty=position.qty, quote_qty=None, client_order_id=None)
            except Exception:
                pass
            del positions[symbol]
            self.state_manager.save_positions(positions)
            pnl = (price - position.entry_price) * position.qty
            try:
                if self.trade_logger is not None:
                    self.trade_logger.log_fill(symbol=symbol, side="SELL", price=price, qty=position.qty, fee=0.0, fee_asset=None, order_id=None, client_order_id=None)
                    pnl_pct = (price / position.entry_price - 1.0) if position.entry_price > 0 else 0.0
                    self.trade_logger.log_trade(symbol=symbol, entry_price=position.entry_price, exit_price=price, qty=position.qty, pnl=pnl, pnl_pct=pnl_pct)
            except Exception:
                pass
            self.notifier.send(f"🛑 SELL {symbol} @ ${price:.4f}\nPnL: ${pnl:.2f}")
        except Exception as exc:
            logging.exception(f"Failed to place SELL order for {symbol}: {exc}")
            self.notifier.send(f"❌ SELL FAILED for {symbol}: {exc}")


