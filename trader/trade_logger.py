import csv
import json
import os
import time
from typing import Dict, Iterable, Optional


class TradeLogger:
    """File-based logger for orders, fills, trades, equity, and summary.

    Creates a directory under base_dir/run_id and appends rows to CSV files
    with headers auto-created on first write.
    """

    def __init__(self, *, base_dir: str, run_id: str, mode: str = "SIMULATED"):
        self.base_dir = os.path.join(base_dir, run_id)
        self.mode = str(mode).upper()
        os.makedirs(self.base_dir, exist_ok=True)

    # -------------- public API --------------
    def log_order(self, *, symbol: str, side: str, price: float, qty: float, quote_qty: Optional[float] = None, client_order_id: Optional[str] = None) -> None:
        self._write_csv_row(
            filename="orders.csv",
            headers=("ts", "mode", "symbol", "side", "price", "qty", "quote_qty", "client_order_id"),
            row={
                "ts": self._ts_ms(),
                "mode": self.mode,
                "symbol": symbol,
                "side": side,
                "price": float(price),
                "qty": float(qty),
                "quote_qty": float(quote_qty) if quote_qty is not None else "",
                "client_order_id": client_order_id or "",
            },
        )

    def log_fill(self, *, symbol: str, side: str, price: float, qty: float, fee: float = 0.0, fee_asset: Optional[str] = None, order_id: Optional[str] = None, client_order_id: Optional[str] = None) -> None:
        self._write_csv_row(
            filename="fills.csv",
            headers=("ts", "mode", "symbol", "side", "price", "qty", "fee", "fee_asset", "order_id", "client_order_id"),
            row={
                "ts": self._ts_ms(),
                "mode": self.mode,
                "symbol": symbol,
                "side": side,
                "price": float(price),
                "qty": float(qty),
                "fee": float(fee),
                "fee_asset": fee_asset or "",
                "order_id": order_id or "",
                "client_order_id": client_order_id or "",
            },
        )

    def log_trade(self, *, symbol: str, entry_price: float, exit_price: float, qty: float, pnl: float, pnl_pct: float) -> None:
        self._write_csv_row(
            filename="trades.csv",
            headers=("ts", "mode", "symbol", "entry_price", "exit_price", "qty", "pnl", "pnl_pct"),
            row={
                "ts": self._ts_ms(),
                "mode": self.mode,
                "symbol": symbol,
                "entry_price": float(entry_price),
                "exit_price": float(exit_price),
                "qty": float(qty),
                "pnl": float(pnl),
                "pnl_pct": float(pnl_pct),
            },
        )

    def log_equity_point(self, *, equity: float) -> None:
        self._write_csv_row(
            filename="equity.csv",
            headers=("ts", "mode", "equity"),
            row={
                "ts": self._ts_ms(),
                "mode": self.mode,
                "equity": float(equity),
            },
        )

    def log_event(self, message: str) -> None:
        path = os.path.join(self.base_dir, "events.log")
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"{int(self._ts_ms())}\t{self.mode}\t{message}\n")

    def save_summary(self, summary: Dict) -> None:
        path = os.path.join(self.base_dir, "summary.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

    # -------------- internals --------------
    def _write_csv_row(self, *, filename: str, headers: Iterable[str], row: Dict) -> None:
        path = os.path.join(self.base_dir, filename)
        file_exists = os.path.exists(path)
        with open(path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(headers))
            if not file_exists:
                writer.writeheader()
            writer.writerow(row)

    @staticmethod
    def _ts_ms() -> int:
        return int(time.time() * 1000)


