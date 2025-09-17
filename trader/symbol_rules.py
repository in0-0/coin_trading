from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class SymbolFilters:
    lot_step_size: float
    lot_min_qty: float
    min_notional: float
    price_tick_size: float


def _parse_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def get_symbol_filters(client: Any, symbol: str, cache: Optional[Dict[str, SymbolFilters]] = None) -> SymbolFilters:
    if cache is not None and symbol in cache:
        return cache[symbol]

    info = client.get_symbol_info(symbol)
    lot_step_size = 0.0
    lot_min_qty = 0.0
    min_notional = 0.0
    price_tick_size = 0.0

    for f in info.get("filters", []):
        ftype = f.get("filterType")
        if ftype == "LOT_SIZE":
            lot_step_size = _parse_float(f.get("stepSize"))
            lot_min_qty = _parse_float(f.get("minQty"))
        elif ftype == "MIN_NOTIONAL":
            min_notional = _parse_float(f.get("minNotional"))
        elif ftype == "PRICE_FILTER":
            price_tick_size = _parse_float(f.get("tickSize"))

    sf = SymbolFilters(
        lot_step_size=lot_step_size,
        lot_min_qty=lot_min_qty,
        min_notional=min_notional,
        price_tick_size=price_tick_size,
    )
    if cache is not None:
        cache[symbol] = sf
    return sf


def round_qty_to_step(qty: float, step_size: float) -> float:
    if step_size <= 0:
        return qty
    # Binance requires truncation to step size increments
    increments = int(qty / step_size)
    return round(increments * step_size, 8)


def round_price_to_tick(price: float, tick_size: float) -> float:
    if tick_size <= 0:
        return price
    increments = int(price / tick_size)
    return round(increments * tick_size, 8)


def validate_min_notional(price: float, qty: float, min_notional: float) -> bool:
    if min_notional <= 0:
        return True
    return (price * qty) >= min_notional


