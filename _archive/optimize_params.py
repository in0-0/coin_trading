#!/usr/bin/env python3
"""
optimize_params.py
- Requires: data/<SYMBOL>_1m.csv for SYMBOL in SYMBOLS
- Performs:
  1) optional dense grid sweep for ATR_MULTIPLIER & RISK_PER_TRADE
  2) Optuna Bayesian optimization for: ATR_MULTIPLIER, RISK_PER_TRADE, TF weights, STRAT weights, ENTER_THRESHOLD
- Outputs results to ./out (best params, nav csv, trades sample)
"""

import os, argparse, json
from datetime import timedelta
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import optuna
from tqdm import tqdm

# ---------------- CONFIG ----------------
SYMBOLS = ["BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","XRPUSDT"]
DATA_DIR = "./data"
OUT_DIR = "./out_opt"
BASE_CAPITAL = 10000.0
EXEC_TF = "5min"    # execution timeframe
TF_RULES = {"1min":"1min","5min":"5min","15min":"15min","1H":"1H","4H":"4H","1D":"1D"}
# default TF order for weights
TF_ORDER = ["4H","1H","15min","5min","1min"]
# defaults for other constants
FEE_RATE = 0.0008
SLIPPAGE = 0.0005
MAX_SYMBOL_WEIGHT = 0.20
MAX_CONCURRENT_POS = 3
MIN_ORDER_USDT = 10.0
ATR_PERIOD = 14
MIN_STOP_DISTANCE = 0.5
# -----------------------------------------

os.makedirs(OUT_DIR, exist_ok=True)

# ---------- helpers (indicators + signals) -------------
def ema(series, span): return series.ewm(span=span, adjust=False).mean()
def rsi(series, period=14):
    delta = series.diff()
    up = delta.clip(lower=0).rolling(period).mean()
    down = -delta.clip(upper=0).rolling(period).mean()
    rs = up / down
    return 100 - (100 / (1 + rs))
def bollinger(series, n=20, k=2):
    ma = series.rolling(n).mean(); std = series.rolling(n).std()
    return ma, ma + k*std, ma - k*std

def compute_atr(df_tf, period=14):
    high = df_tf['high']; low = df_tf['low']; close = df_tf['close']
    prev = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev).abs()
    tr3 = (low - prev).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(period).mean()

def signals_for_tf(df_tf):
    close = df_tf['close']
    a = ema(close, 9); b = ema(close, 26)
    s_ema = np.where(a > b, 1, -1)
    rsival = rsi(close, 14)
    s_rsi = np.where(rsival < 30, 1, np.where(rsival > 70, -1, 0))
    ma, up, lo = bollinger(close, 20, 2)
    s_bb = np.where(close < lo, 1, np.where(close > up, 1, 0))
    return pd.DataFrame({"ema":s_ema, "rsi":s_rsi, "bb":s_bb}, index=df_tf.index)

def build_ensemble_and_atr(df_1m, tf_weights, strat_weights, exec_tf=EXEC_TF):
    idx = df_1m.index
    accum = pd.DataFrame(index=idx)
    for tf_label, tf_rule in TF_RULES.items():
        df_tf = df_1m.resample(tf_rule).agg({'open':'first','high':'max','low':'min','close':'last','volume':'sum'}).dropna()
        sig = signals_for_tf(df_tf)
        sig_1 = sig.reindex(idx, method='ffill').fillna(0)
        tfw = tf_weights.get(tf_label, 0)
        for strat, w in strat_weights.items():
            accum[f"{tf_label}_{strat}"] = sig_1[strat] * (w * tfw)
    ensemble = accum.sum(axis=1)
    ensemble_exec = ensemble.resample(exec_tf).last().dropna()
    df_exec = df_1m.resample(exec_tf).agg({'open':'first','high':'max','low':'min','close':'last','volume':'sum'}).dropna()
    df_exec = df_exec.loc[ensemble_exec.index]
    atr = compute_atr(df_exec, ATR_PERIOD)
    return ensemble_exec, df_exec[['open','high','low','close','volume']], atr

# --------- Backtest engine (ATR sizing) ----------
def backtest_portfolio(data_dfs, atr_mul, risk_per_trade, tf_weights, strat_weights, enter_threshold):
    # prepare ensembles
    ensemble = {}; df_exec = {}; atr_exec = {}
    for s, df in data_dfs.items():
        ens, dfe, atr = build_ensemble_and_atr(df, tf_weights, strat_weights, EXEC_TF)
        ensemble[s] = ens; df_exec[s] = dfe; atr_exec[s] = atr
    # align time
    common_index = ensemble[next(iter(ensemble))].index
    for s in ensemble:
        ensemble[s] = ensemble[s].reindex(common_index).ffillna().fillna(0)
        df_exec[s] = df_exec[s].reindex(common_index).ffill()
        atr_exec[s] = atr_exec[s].reindex(common_index).ffill()
    times = common_index
    cash = BASE_CAPITAL
    positions = {s:0.0 for s in SYMBOLS}
    stop_price = {s:None for s in SYMBOLS}
    nav_hist = []; trades = []

    for t in times:
        total_pos_value = sum((positions[s] * df_exec[s].loc[t,'close']) if positions[s] > 0 else 0.0 for s in SYMBOLS)
        nav = cash + total_pos_value
        nav_hist.append({"time":t, "nav":nav})
        # stops
        for s in SYMBOLS:
            if positions[s] > 0:
                p = df_exec[s].loc[t,'close']; sp = stop_price[s]
                if sp is not None and p <= sp:
                    qty = positions[s]
                    proceeds = qty * p * (1 - SLIPPAGE - FEE_RATE)
                    cash += proceeds
                    trades.append({"time":t,"symbol":s,"side":"STOP_SELL","price":p,"qty":qty,"cash":cash})
                    positions[s] = 0.0; stop_price[s] = None
        # regular exit
        for s in SYMBOLS:
            score = ensemble[s].loc[t]; price = df_exec[s].loc[t,'close']
            if positions[s] > 0 and score <= 0:
                qty = positions[s]
                proceeds = qty * price * (1 - SLIPPAGE - FEE_RATE)
                cash += proceeds
                trades.append({"time":t,"symbol":s,"side":"SELL","price":price,"qty":qty,"cash":cash})
                positions[s] = 0.0; stop_price[s] = None
        # entries
        candidates = [(s, ensemble[s].loc[t]) for s in SYMBOLS if positions[s] == 0]
        candidates = [c for c in candidates if c[1] >= enter_threshold]
        candidates.sort(key=lambda x: x[1], reverse=True)
        for s, score in candidates:
            if sum(1 for ss in SYMBOLS if positions[ss] > 0) >= MAX_CONCURRENT_POS: break
            price = df_exec[s].loc[t,'close']; atr = atr_exec[s].loc[t]
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
    if df_nav.empty: return {"start":None,"end":None,"total_return":None,"cagr":None,"mdd":None,"sharpe":None}
    df = df_nav.copy()
    df['ret'] = df['nav'].pct_change().fillna(0)
    total_return = df['nav'].iloc[-1] / df['nav'].iloc[0] - 1
    days = (df.index[-1] - df.index[0]).days + 1
    cagr = (df['nav'].iloc[-1] / df['nav'].iloc[0]) ** (365.0/days) - 1 if days>0 else np.nan
    cummax = df['nav'].cummax(); drawdown = df['nav'] / cummax - 1; mdd = drawdown.min()
    df_daily = df.resample('1D').last().ffill(); daily_ret = df_daily['nav'].pct_change().dropna()
    sharpe = (daily_ret.mean() / daily_ret.std()) * (365**0.5) if daily_ret.std() != 0 else np.nan
    return {"start":df['nav'].iloc[0],"end":df['nav'].iloc[-1],"total_return":total_return,"cagr":cagr,"mdd":mdd,"sharpe":sharpe}

# ---------- Optuna objective ----------
def objective(trial, data_dfs):
    # sample params
    atr_mul = trial.suggest_float("atr_mul", 0.8, 4.0, step=0.1)
    risk = trial.suggest_float("risk", 0.002, 0.03, step=0.001)  # 0.2% ~ 3%
    # TF weights: Dirichlet-like sampling but we'll sample raw positives and normalize
    raw_tf = [trial.suggest_float(f"tf_{i}", 0.0, 1.0) for i in range(len(TF_ORDER))]
    total = sum(raw_tf)
    tf_weights = {tf: raw_tf[i]/total for i, tf in enumerate(TF_ORDER)}
    # strategy weights (3) normalize
    raw_strat = [trial.suggest_float(f"strat_{i}", 0.0, 1.0) for i in range(3)]
    s_total = sum(raw_strat) or 1.0
    strat_weights = {"ema": raw_strat[0]/s_total, "rsi": raw_strat[1]/s_total, "bb": raw_strat[2]/s_total}
    enter_threshold = trial.suggest_float("enter_thr", 0.3, 1.2, step=0.05)
    # run backtest
    df_nav, trades, metrics = backtest_portfolio(data_dfs, atr_mul, risk, tf_weights, strat_weights, enter_threshold)
    sharpe = metrics.get("sharpe") or -999.0
    # penalize extremely large drawdowns or NaNs
    if pd.isna(sharpe): sharpe = -999.0
    # use sharpe as objective (maximize)
    trial.set_user_attr("metrics", metrics)
    return sharpe

# ---------- CLI & runner ----------
def load_data():
    data_dfs = {}
    for s in SYMBOLS:
        p = os.path.join(DATA_DIR, f"{s}_1m.csv")
        if not os.path.exists(p):
            raise FileNotFoundError(f"{p} not found. Please place CSVs in {DATA_DIR}")
        df = pd.read_csv(p, parse_dates=['datetime']).set_index('datetime')
        data_dfs[s] = df[['open','high','low','close','volume']]
    return data_dfs

def dense_grid_search(data_dfs, atr_list, risk_list, tf_weights=None, strat_weights=None, enter_thr=0.6):
    rows = []
    for atr in atr_list:
        for risk in risk_list:
            df_nav, trades, metrics = backtest_portfolio(data_dfs, atr, risk, tf_weights or {"4H":0.35,"1H":0.25,"15min":0.18,"5min":0.12,"1min":0.10},
                                                         strat_weights or {"ema":0.3,"rsi":0.3,"bb":0.4}, enter_thr)
            row = {"atr":atr, "risk":risk}
            row.update(metrics)
            rows.append(row)
    df = pd.DataFrame(rows).sort_values(by=['sharpe','total_return'], ascending=[False,False])
    df.to_csv(os.path.join(OUT_DIR, "dense_grid_summary.csv"), index=False)
    return df

def main(trials=100):
    data_dfs = load_data()
    # optional dense grid first (coarse)
    atr_coarse = list(np.round(np.linspace(1.0,3.0,9),2))
    risk_coarse = [0.005, 0.01, 0.02]
    print("Running coarse dense grid...")
    dense_grid_search(data_dfs, atr_coarse, risk_coarse)
    # Optuna Bayesian optimization
    print("Starting Optuna study...")
    study = optuna.create_study(direction="maximize")
    study.optimize(lambda t: objective(t, data_dfs), n_trials=trials, show_progress_bar=True)
    print("Best trial:", study.best_trial.params)
    # store best config and run a final backtest for outputs
    best = study.best_trial.params
    atr_mul = best['atr_mul']; risk = best['risk']
    # reconstruct tf and strat weights
    raw_tf = [best[f"tf_{i}"] for i in range(len(TF_ORDER))]
    tf_weights = {TF_ORDER[i]: raw_tf[i]/sum(raw_tf) for i in range(len(TF_ORDER))}
    raw_strat = [best[f"strat_{i}"] for i in range(3)]
    s_total = sum(raw_strat) or 1.0
    strat_weights = {"ema": raw_strat[0]/s_total, "rsi": raw_strat[1]/s_total, "bb": raw_strat[2]/s_total}
    enter_thr = best.get("enter_thr", 0.6)
    df_nav, trades, metrics = backtest_portfolio(data_dfs, atr_mul, risk, tf_weights, strat_weights, enter_thr)
    # save outputs
    with open(os.path.join(OUT_DIR, "best_params.json"), "w") as f:
        json.dump({"atr_mul":atr_mul,"risk":risk,"tf_weights":tf_weights,"strat_weights":strat_weights,"enter_thr":enter_thr, "metrics":metrics}, f, indent=2)
    df_nav.to_csv(os.path.join(OUT_DIR, "best_nav.csv"))
    pd.DataFrame(trades).to_csv(os.path.join(OUT_DIR, "best_trades_full.csv"), index=False)
    plt.figure(figsize=(10,4)); plt.plot(df_nav.index, df_nav['nav']); plt.title("Best NAV"); plt.savefig(os.path.join(OUT_DIR,"best_nav_optuna.png"), dpi=150)
    print("Outputs saved to", OUT_DIR)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--trials", type=int, default=100, help="Optuna trials count")
    args = parser.parse_args()
    main(trials=args.trials)