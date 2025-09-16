#!/usr/bin/env python3
"""
collect_and_grid_backtest.py
- Fetches 1m klines from Binance for a list of symbols (recent N days)
- Saves CSVs to data/
- Runs ATR-based portfolio backtester with grid search over ATR_MULTIPLIER and RISK_PER_TRADE
- Saves results to out/

Usage:
  - Set BINANCE_API_KEY and BINANCE_API_SECRET as env vars (recommended)
  - python collect_and_grid_backtest.py
"""

import os, time, math
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from binance.client import Client
from tqdm import tqdm
import matplotlib.pyplot as plt
from dotenv import load_dotenv

# -------------------- CONFIG --------------------
SYMBOLS = ["BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","XRPUSDT"]
DATA_DIR = "./data"
OUT_DIR = "./out"
DAYS_TO_FETCH = 90   # recent N days of 1m data
# Grid to search
ATR_MUL_GRID = [1.0, 1.5, 2.0, 2.5, 3.0]
RISK_GRID = [0.005, 0.01, 0.02]  # 0.5%, 1%, 2%
# Backtest engine params (defaults; you may change)
BASE_CAPITAL = 10000.0
EXEC_TF = "5min"          # execution timeframe (pandas resample rule)
TF_RULES = {"1min":"1min","5min":"5min","15min":"15min","1H":"1H","4H":"4H","1D":"1D"}
TF_WEIGHTS = {"4H":0.35,"1H":0.25,"15min":0.18,"5min":0.12,"1min":0.10}
STRAT_WEIGHTS = {"ema":0.3,"rsi":0.3,"bb":0.4}
FEE_RATE = 0.0008
SLIPPAGE = 0.0005
ENTER_THRESHOLD = 0.6
MAX_SYMBOL_WEIGHT = 0.20
MAX_CONCURRENT_POS = 3
MIN_ORDER_USDT = 10.0
ATR_PERIOD = 14
ATR_MULTIPLIER_DEFAULT = 2.0
MIN_STOP_DISTANCE = 0.5
# ------------------------------------------------

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(OUT_DIR, exist_ok=True)
load_dotenv()

# ------- Binance client -------
API_KEY = os.getenv("BINANCE_API_KEY", None)
API_SECRET = os.getenv("BINANCE_SECRET_KEY", None)

print(API_KEY, API_SECRET)
client = Client(API_KEY, API_SECRET) if API_KEY and API_SECRET else Client()

# ---------- Helpers ----------
def fetch_1m_klines_to_csv(symbol, days=DAYS_TO_FETCH):
    """Fetch 1m klines for 'days' recent days and save CSV to data/<symbol>_1m.csv"""
    out_path = os.path.join(DATA_DIR, f"{symbol}_1m.csv")
    if os.path.exists(out_path):
        print(f"[skip] {out_path} exists.")
        return out_path
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(days=days)
    # Binance get_historical_klines supports start_str, end_str; it will paginate internally for many libs.
    print(f"Fetching {symbol} 1m from {start_time} to {end_time} ...")
    klines = []
    # Use client.get_historical_klines with 1m interval; it returns list of lists
    # To avoid server overload, fetch day-by-day in loop
    cur_start = start_time
    last_cur_start = cur_start
    dup_count = 0
    while (cur_start < end_time) or dup_count < 2:
        cur_end = min(cur_start + timedelta(days=7), end_time)  # fetch at most 7 days per call to be safe
        tries = 0
        while True:
            try:
                # print(f"Fetching Date: {cur_start} to {cur_end} ...")
                data = client.get_klines(symbol=symbol, interval=Client.KLINE_INTERVAL_1MINUTE,
                                         startTime=int(cur_start.timestamp()*1000),
                                         endTime=int(cur_end.timestamp()*1000),
                                         limit=1000)
                break
            except Exception as e:
                tries += 1
                if tries > 5:
                    raise
                print("Warning: fetch error, retrying...", str(e))
                time.sleep(1 + tries)
        if not data:
            cur_start = cur_end
            continue
        klines.extend(data)
        # next start: last fetched open time + 1 minute
        last_open = klines[-1][0] / 1000.0
        fst_open = data[0][0] / 1000.0
        
        cur_start = datetime.fromtimestamp(last_open + 60)
        print(f"Real Fetched Date: {datetime.fromtimestamp(fst_open)} to {datetime.fromtimestamp(last_open)}, next start {cur_start}")

        if cur_start >= last_cur_start:
            dup_count += 1
        else:
            last_cur_start = cur_start
        time.sleep(0.2)  # rate-limit cushion
    # convert to DataFrame
    df = pd.DataFrame(klines, columns=[
        "open_time","open","high","low","close","volume","close_time",
        "quote_asset_volume","num_trades","taker_base","taker_quote","ignore"])
    df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
    df = df.rename(columns={"open_time":"datetime"})
    df = df[['datetime','open','high','low','close','volume']]
    df.to_csv(out_path, index=False)
    print(f"Saved {out_path} ({len(df)} rows)")
    return out_path

# basic indicators
def ema(series, span): return series.ewm(span=span, adjust=False).mean()
def rsi(series, period=14):
    delta = series.diff()
    up = delta.clip(lower=0).rolling(period).mean()
    down = -delta.clip(upper=0).rolling(period).mean()
    rs = up / down
    return 100 - (100 / (1 + rs))
def bollinger(series, n=20, k=2):
    ma = series.rolling(n).mean()
    std = series.rolling(n).std()
    upper = ma + k*std
    lower = ma - k*std
    return ma, upper, lower

def compute_atr(df_tf, period=14):
    high = df_tf['high']; low = df_tf['low']; close = df_tf['close']
    prev = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev).abs()
    tr3 = (low - prev).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()
    return atr

def signals_for_tf(df_tf):
    close = df_tf['close']
    a = ema(close, 9); b = ema(close, 26)
    s_ema = np.where(a > b, 1, -1)
    rsival = rsi(close, 14)
    s_rsi = np.where(rsival < 30, 1, np.where(rsival > 70, -1, 0))
    ma, up, lo = bollinger(close, 20, 2)
    s_bb = np.where(close < lo, 1, np.where(close > up, 1, 0))
    return pd.DataFrame({"ema":s_ema, "rsi":s_rsi, "bb":s_bb}, index=df_tf.index)

def build_ensemble_and_atr_from_df(df_1m, exec_tf=EXEC_TF):
    accum = pd.DataFrame(index=df_1m.index)
    for tf_label, tf_rule in TF_RULES.items():
        df_tf = df_1m.resample(tf_rule).agg({'open':'first','high':'max','low':'min','close':'last','volume':'sum'}).dropna()
        sig = signals_for_tf(df_tf)
        sig_1 = sig.reindex(df_1m.index, method='ffill').fillna(0)
        tfw = TF_WEIGHTS.get(tf_label, 0)
        for strat, w in STRAT_WEIGHTS.items():
            accum[f"{tf_label}_{strat}"] = sig_1[strat] * (w * tfw)
    ensemble = accum.sum(axis=1)
    ensemble_exec = ensemble.resample(exec_tf).last().dropna()
    df_exec = df_1m.resample(exec_tf).agg({'open':'first','high':'max','low':'min','close':'last','volume':'sum'}).dropna()
    df_exec = df_exec.loc[ensemble_exec.index]
    atr = compute_atr(df_exec, ATR_PERIOD)
    return ensemble_exec, df_exec, atr

# Backtest with ATR sizing
def run_backtest_for_params(data_dfs, atr_mul, risk_per_trade):
    ensemble = {}; df_exec_price = {}; atr_exec = {}
    for s, df in data_dfs.items():
        ens, df_exec, atr = build_ensemble_and_atr_from_df(df, exec_tf=EXEC_TF)
        ensemble[s] = ens
        df_exec_price[s] = df_exec
        atr_exec[s] = atr
    # align common time index
    common_idx = ensemble[next(iter(ensemble))].index
    for s in ensemble:
        ensemble[s] = ensemble[s].reindex(common_idx).fillna(method='ffill').fillna(0)
        df_exec_price[s] = df_exec_price[s].reindex(common_idx).ffill()
        atr_exec[s] = atr_exec[s].reindex(common_idx).ffill()
    times = common_idx
    cash = BASE_CAPITAL
    positions = {s:0.0 for s in SYMBOLS}
    stop_price = {s:None for s in SYMBOLS}
    nav_hist = []; trades = []
    for t in times:
        total_pos_value = sum((positions[s] * df_exec_price[s].loc[t,'close']) if positions[s] > 0 else 0.0 for s in SYMBOLS)
        nav = cash + total_pos_value
        nav_hist.append({"time":t, "nav":nav})
        # stops
        for s in SYMBOLS:
            if positions[s] > 0:
                p = df_exec_price[s].loc[t,'close']
                sp = stop_price[s]
                if sp is not None and p <= sp:
                    qty = positions[s]
                    proceeds = qty * p * (1 - SLIPPAGE - FEE_RATE)
                    cash += proceeds
                    trades.append({"time":t,"symbol":s,"side":"STOP_SELL","price":p,"qty":qty,"cash":cash})
                    positions[s] = 0.0; stop_price[s] = None
        # exits by ensemble
        for s in SYMBOLS:
            score = ensemble[s].loc[t]
            price = df_exec_price[s].loc[t,'close']
            if positions[s] > 0 and score <= 0:
                qty = positions[s]
                proceeds = qty * price * (1 - SLIPPAGE - FEE_RATE)
                cash += proceeds
                trades.append({"time":t,"symbol":s,"side":"SELL","price":price,"qty":qty,"cash":cash})
                positions[s] = 0.0; stop_price[s] = None
        # entries
        candidates = [(s, ensemble[s].loc[t]) for s in SYMBOLS if positions[s] == 0]
        candidates = [c for c in candidates if c[1] >= ENTER_THRESHOLD]
        candidates.sort(key=lambda x: x[1], reverse=True)
        for s, score in candidates:
            if sum(1 for ss in SYMBOLS if positions[ss] > 0) >= MAX_CONCURRENT_POS: break
            price = df_exec_price[s].loc[t,'close']; atr = atr_exec[s].loc[t]
            if pd.isna(atr) or atr <= 0: continue
            stop_distance = atr * atr_mul
            if stop_distance < MIN_STOP_DISTANCE: stop_distance = MIN_STOP_DISTANCE
            risk_usdt = nav * risk_per_trade
            qty = risk_usdt / stop_distance
            max_alloc = BASE_CAPITAL * MAX_SYMBOL_WEIGHT
            max_qty_by_alloc = (max_alloc * (1 - SLIPPAGE - FEE_RATE)) / price
            qty = min(qty, max_qty_by_alloc)
            cost = qty * price * (1 + SLIPPAGE + FEE_RATE)
            if qty * price < MIN_ORDER_USDT or cost > cash - 1.0: continue
            cash -= cost; positions[s] = qty
            stop_price[s] = price - stop_distance
            trades.append({"time":t,"symbol":s,"side":"BUY","price":price,"qty":qty,"stop_price":stop_price[s],"cash":cash})
    df_nav = pd.DataFrame(nav_hist).set_index("time")
    metrics = compute_metrics(df_nav)
    return df_nav, trades, metrics

def compute_metrics(df_nav):
    df = df_nav.copy()
    if df.empty: return {"start":None,"end":None,"total_return":None,"cagr":None,"mdd":None,"sharpe":None}
    df['ret'] = df['nav'].pct_change().fillna(0)
    total_return = df['nav'].iloc[-1] / df['nav'].iloc[0] - 1
    days = (df.index[-1] - df.index[0]).days + 1
    cagr = (df['nav'].iloc[-1] / df['nav'].iloc[0]) ** (365.0/days) - 1 if days>0 else np.nan
    cummax = df['nav'].cummax(); drawdown = df['nav'] / cummax - 1; mdd = drawdown.min()
    df_daily = df.resample('1D').last().ffill(); daily_ret = df_daily['nav'].pct_change().dropna()
    sharpe = (daily_ret.mean() / daily_ret.std()) * (365**0.5) if daily_ret.std() != 0 else np.nan
    return {"start":df['nav'].iloc[0],"end":df['nav'].iloc[-1],"total_return":total_return,"cagr":cagr,"mdd":mdd,"sharpe":sharpe}

# ----------------- Main -----------------
def main():
    # 1) fetch data
    data_dfs = {}
    for s in SYMBOLS:
        csv_path = fetch_1m_klines_to_csv(s, DAYS_TO_FETCH)
        df = pd.read_csv(csv_path, parse_dates=['datetime']).set_index('datetime')
        data_dfs[s] = df

    # 2) grid search
    results = []
    total = len(ATR_MUL_GRID) * len(RISK_GRID)
    cnt = 0
    for atr_mul in ATR_MUL_GRID:
        for risk in RISK_GRID:
            cnt += 1
            print(f"[{cnt}/{total}] Running grid: ATR_mul={atr_mul}, risk={risk}")
            df_nav, trades, metrics = run_backtest_for_params(data_dfs, atr_mul, risk)
            metrics['atr_mul'] = atr_mul; metrics['risk'] = risk
            results.append(metrics)
            # save sample nav & trades for this run (optional)
            run_prefix = f"atr{atr_mul}_risk{int(risk*10000)}"
            df_nav.to_csv(os.path.join(OUT_DIR, f"{run_prefix}_nav.csv"))
            pd.DataFrame(trades).to_csv(os.path.join(OUT_DIR, f"{run_prefix}_trades.csv"), index=False)
    df_res = pd.DataFrame(results).sort_values(by=['sharpe','total_return'], ascending=[False,False])
    df_res.to_csv(os.path.join(OUT_DIR, "grid_search_summary.csv"), index=False)
    print("Grid search completed. Summary saved to:", os.path.join(OUT_DIR, "grid_search_summary.csv"))
    # generate best-nav plot
    best = df_res.iloc[0]
    best_atr = best['atr_mul']; best_risk = best['risk']
    df_nav_best, trades_best, _ = run_backtest_for_params(data_dfs, best_atr, best_risk)
    plt.figure(figsize=(10,4)); plt.plot(df_nav_best.index, df_nav_best['nav']); plt.title(f"Best NAV (atr={best_atr}, risk={best_risk})")
    plt.savefig(os.path.join(OUT_DIR, "best_nav.png"), dpi=150)
    pd.DataFrame(trades_best).head(500).to_csv(os.path.join(OUT_DIR, "best_trades_sample.csv"), index=False)
    print("Best run outputs saved to out/")

if __name__ == "__main__":
    main()