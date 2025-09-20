
import pandas as pd


class PositionSizer:
    def __init__(self, risk_per_trade: float, max_symbol_weight: float, min_order_usdt: float):
        self.risk_per_trade = risk_per_trade
        self.max_symbol_weight = max_symbol_weight
        self.min_order_usdt = min_order_usdt

    def compute_spend_amount(self, usdt_balance: float, market_data: pd.DataFrame) -> float | None:
        if market_data is None or market_data.empty:
            return None
        risk_usdt = usdt_balance * self.risk_per_trade
        spend_amount = risk_usdt * 10.0
        max_alloc = usdt_balance * self.max_symbol_weight
        spend_amount = min(spend_amount, max_alloc, usdt_balance * 0.95)
        return spend_amount if spend_amount >= self.min_order_usdt else None





def kelly_position_size(
    *,
    capital: float,
    win_rate: float,
    avg_win: float,
    avg_loss: float,
    score: float,
    max_score: float,
    f_max: float = 0.2,
    pos_min: float = 0.0,
    pos_max: float = 1.0,
):
    """Compute position notional using Kelly fraction scaled by signal confidence.

    Returns notional amount (same units as capital).
    """
    if capital <= 0:
        return 0.0
    if avg_win <= 0 or avg_loss <= 0 or max_score <= 0:
        return 0.0
    p = max(0.0, min(1.0, win_rate))
    q = 1.0 - p
    b = avg_win / avg_loss
    if b <= 0:
        return 0.0
    # Kelly fraction: f* = (b*p - q) / b
    f_star = (b * p - q) / b
    f_star = max(0.0, min(f_star, f_max))
    # Signal confidence
    confidence = min(1.0, max(0.0, abs(score) / max_score))
    fraction = f_star * confidence
    fraction = max(pos_min, min(fraction, pos_max))
    return capital * fraction
