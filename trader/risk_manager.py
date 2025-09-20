"""
Risk management utilities for initial stop-loss and take-profit placement.

Provides a pure function to compute an initial bracket (SL/TP) based on ATR.
"""



def compute_initial_bracket(entry: float, atr: float, side: str, k_sl: float, rr: float) -> tuple[float, float]:
    """Compute initial stop-loss and take-profit prices based on ATR.

    Args:
        entry: Entry price.
        atr: Average True Range value at entry.
        side: "long" or "short".
        k_sl: Multiplier for ATR to set stop distance.
        rr: Risk-reward ratio (take-profit distance = rr * stop distance).

    Returns:
        A tuple of (stop_loss, take_profit).

    Raises:
        ValueError: If inputs are invalid or side is not recognized.
    """
    if atr < 0 or k_sl < 0 or rr < 0:
        raise ValueError("atr, k_sl, rr must be non-negative")
    distance = k_sl * atr
    if side == "long":
        stop_loss = entry - distance
        take_profit = entry + rr * distance
        return float(stop_loss), float(take_profit)
    if side == "short":
        stop_loss = entry + distance
        take_profit = entry - rr * distance
        return float(stop_loss), float(take_profit)
    raise ValueError("side must be 'long' or 'short'")


