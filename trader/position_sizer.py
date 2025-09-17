from typing import Optional
import pandas as pd


class PositionSizer:
    def __init__(self, risk_per_trade: float, max_symbol_weight: float, min_order_usdt: float):
        self.risk_per_trade = risk_per_trade
        self.max_symbol_weight = max_symbol_weight
        self.min_order_usdt = min_order_usdt

    def compute_spend_amount(self, usdt_balance: float, market_data: pd.DataFrame) -> Optional[float]:
        if market_data is None or market_data.empty:
            return None
        risk_usdt = usdt_balance * self.risk_per_trade
        spend_amount = risk_usdt * 10.0
        max_alloc = usdt_balance * self.max_symbol_weight
        spend_amount = min(spend_amount, max_alloc, usdt_balance * 0.95)
        return spend_amount if spend_amount >= self.min_order_usdt else None




