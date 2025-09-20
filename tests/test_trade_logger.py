import json
import os
import tempfile
from importlib import import_module


def _read_lines(path):
    with open(path) as f:
        return [line.strip() for line in f.readlines()]


def test_tradelogger_writes_headers_and_appends_rows():
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            mod = import_module("trader.trade_logger")
            TradeLogger = mod.TradeLogger
        except Exception:
            assert False, "TradeLogger not implemented yet"

        logger = TradeLogger(base_dir=tmpdir, run_id="test_run", mode="SIMULATED")
        logger.log_order(symbol="BTCUSDT", side="BUY", price=50000.0, qty=0.01, client_order_id="cid-1")
        logger.log_order(symbol="BTCUSDT", side="SELL", price=51000.0, qty=0.01, client_order_id="cid-2")

        orders_csv = os.path.join(tmpdir, "test_run", "orders.csv")
        assert os.path.exists(orders_csv)
        lines = _read_lines(orders_csv)
        assert len(lines) >= 3  # header + 2 rows
        assert "symbol,side,price,qty" in lines[0]

        logger.log_fill(symbol="BTCUSDT", side="BUY", price=50010.0, qty=0.01, fee=0.01, fee_asset="USDT", order_id="o-1", client_order_id="cid-1")
        fills_csv = os.path.join(tmpdir, "test_run", "fills.csv")
        assert os.path.exists(fills_csv)

        logger.log_trade(symbol="BTCUSDT", entry_price=50000.0, exit_price=51000.0, qty=0.01, pnl=10.0, pnl_pct=0.02)
        trades_csv = os.path.join(tmpdir, "test_run", "trades.csv")
        assert os.path.exists(trades_csv)

        logger.save_summary({"total_return": 0.02})
        summary_json = os.path.join(tmpdir, "test_run", "summary.json")
        assert os.path.exists(summary_json)
        with open(summary_json) as f:
            data = json.load(f)
        assert "total_return" in data
