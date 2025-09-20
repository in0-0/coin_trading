from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any


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


def get_symbol_filters(client: Any, symbol: str, cache: dict[str, SymbolFilters] | None = None) -> SymbolFilters:
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



# ---------------- Composite Strategy Parameter Overrides ----------------

# In-memory overrides map. Keyed by (symbol, interval). Values are shallow dicts
# that may include nested "weights" dicts. This is intentionally minimal and can
# be later extended to load from TOML under commands/sc/.
COMPOSITE_PARAM_OVERRIDES: dict[tuple[str, str], dict[str, Any]] = {}


def _to_namespace(d: dict[str, Any]) -> SimpleNamespace:
    ns = SimpleNamespace()
    for k, v in d.items():
        setattr(ns, k, v)
    return ns


def _merge_weights(default_w: Any, override_w: Any) -> Any:
    # Accept dict or namespace for weights
    if override_w is None:
        return default_w
    # Convert both to dicts for merging
    def as_dict(obj: Any) -> dict[str, Any]:
        if isinstance(obj, dict):
            return dict(obj)
        # Namespace or any with __dict__
        try:
            return dict(obj.__dict__)
        except Exception:
            return {}

    merged = as_dict(default_w)
    merged.update(as_dict(override_w))
    return _to_namespace(merged)


def resolve_composite_params(symbol: str, interval: str, defaults: Any) -> Any:
    """
    Merge symbol/interval-specific overrides into composite strategy defaults.

    - Shallow-merge for top-level keys
    - Special handling for nested weights (merged by key)
    - Returns a SimpleNamespace-like object preserving attribute-style access
    """
    ov = COMPOSITE_PARAM_OVERRIDES.get((symbol, interval)) or {}
    # Start with defaults as dict
    try:
        base = dict(defaults.__dict__)
    except Exception:
        base = {}

    result: dict[str, Any] = dict(base)
    if "weights" in ov:
        result["weights"] = _merge_weights(base.get("weights"), ov.get("weights"))
    # Copy other scalar overrides
    for k, v in ov.items():
        if k == "weights":
            continue
        result[k] = v
    return _to_namespace(result)
