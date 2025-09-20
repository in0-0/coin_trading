import csv
import json
import os
import time
from collections.abc import Iterable
from datetime import datetime, timezone
try:  # Python 3.9+
    from zoneinfo import ZoneInfo  # type: ignore
except Exception:  # pragma: no cover
    ZoneInfo = None  # type: ignore


class TradeLogger:
    """File-based logger for orders, fills, trades, equity, and summary.

    Creates a directory under base_dir/run_id and appends rows to CSV files
    with headers auto-created on first write.
    """

    def __init__(self, *, base_dir: str, run_id: str, mode: str = "SIMULATED", date_partition: str = "none", tz: str | None = None, date_fmt: str = "%Y%m%d"):
        # Determine base directory with optional date partitioning
        partition = (date_partition or "none").lower()
        target_dir = base_dir
        if partition in ("daily", "day", "date"):
            tz_name = tz or os.getenv("LOG_TZ", "UTC")
            # Resolve timezone; fallback to UTC if not available
            if ZoneInfo is not None:
                try:
                    tzinfo = ZoneInfo(tz_name)
                except Exception:
                    tzinfo = timezone.utc
            else:
                tzinfo = timezone.utc
            date_str = datetime.now(tzinfo).strftime(date_fmt or "%Y%m%d")
            target_dir = os.path.join(base_dir, date_str)
        self.base_dir = os.path.join(target_dir, run_id)
        self.mode = str(mode).upper()
        os.makedirs(self.base_dir, exist_ok=True)

    # -------------- public API --------------
    def log_order(self, *, symbol: str, side: str, price: float, qty: float, quote_qty: float | None = None, client_order_id: str | None = None) -> None:
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

    def log_fill(self, *, symbol: str, side: str, price: float, qty: float, fee: float = 0.0, fee_asset: str | None = None, order_id: str | None = None, client_order_id: str | None = None) -> None:
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

    def save_summary(self, summary: dict) -> None:
        path = os.path.join(self.base_dir, "summary.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

    def save_final_performance(self, performance_data: dict) -> None:
        """최종 성과 데이터를 JSON 파일로 저장합니다."""
        path = os.path.join(self.base_dir, "final_performance.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(performance_data, f, indent=2)

        # 로그에도 기록
        total_return = performance_data.get('total_return_pct', 0.0)
        total_trades = performance_data.get('total_trades', 0)
        win_rate = performance_data.get('win_rate', 0.0)
        self.log_event(f"Final performance saved: {total_return:.1f}% return, "
                      f"{total_trades} trades, "
                      f"Win rate: {win_rate:.1f}%")

    # -------------- internals --------------
    def _write_csv_row(self, *, filename: str, headers: Iterable[str], row: dict) -> None:
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


