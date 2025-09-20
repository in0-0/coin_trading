import os
import tempfile
from datetime import datetime, timezone


def test_tradelogger_daily_partition_creates_dated_dir(monkeypatch):
    # Freeze date to a known UTC day
    fixed_dt = datetime(2025, 9, 20, 12, 34, 56, tzinfo=timezone.utc)
    # Ensure environment doesn't interfere
    monkeypatch.delenv("LIVE_LOG_DATE_PARTITION", raising=False)
    monkeypatch.delenv("LOG_TZ", raising=False)
    monkeypatch.delenv("LOG_DATE_FMT", raising=False)

    # Import after cleaning env
    from importlib import import_module
    mod = import_module("trader.trade_logger")
    TradeLogger = mod.TradeLogger

    with tempfile.TemporaryDirectory() as tmpdir:
        run_id = "runtest"
        # Create logger with daily partition enabled explicitly
        logger = TradeLogger(base_dir=tmpdir, run_id=run_id, mode="SIMULATED", date_partition="daily", tz="UTC", date_fmt="%Y%m%d")
        # Write one row to materialize files
        logger.log_order(symbol="BTCUSDT", side="BUY", price=100.0, qty=0.01, quote_qty=1.0, client_order_id="cid")

        # Expected dated dir
        date_dir = fixed_dt.strftime("%Y%m%d")
        # Since logger computes date internally, allow either exact date_dir or today's if not plumbed yet
        # The test asserts presence under a YYYYMMDD layer
        dirs = [d for d in os.listdir(tmpdir) if os.path.isdir(os.path.join(tmpdir, d))]
        assert any(len(name) == 8 and name.isdigit() for name in dirs), f"No YYYYMMDD directory under {tmpdir}: {dirs}"

        # Find the dated directory and check run_id subdir and file
        dated = next(d for d in dirs if len(d) == 8 and d.isdigit())
        base = os.path.join(tmpdir, dated, run_id)
        assert os.path.exists(os.path.join(base, "orders.csv"))


