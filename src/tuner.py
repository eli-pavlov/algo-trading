import os
import yfinance as yf
import pandas_ta_classic as ta
import optuna
import urllib3
import pandas as pd
import numpy as np
import gc
from functools import partial
from src.database import save_strategy, init_db
from src.broker import Broker

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
TICKERS = ['HOOD', 'AMD', 'AI', 'CVNA', 'PLTR']

def get_stock_data(symbol):
    try:
        df = yf.download(symbol, period="1y", interval="1h", progress=False, threads=False, auto_adjust=False)
        if df.empty: return None
        
        if isinstance(df.columns, pd.MultiIndex): 
            df.columns = df.columns.get_level_values(0)
            
        for c in ["Open", "High", "Low", "Close"]:
            if c in df.columns:
                s = df[c]
                if isinstance(s, pd.DataFrame): s = s.iloc[:, 0]
                df[c] = pd.Series(np.asarray(s).reshape(-1), index=df.index)
        return df
    except: return None

def precompute_indicators(df):
    df = df.copy()
    try:
        adx_df = ta.adx(df['High'], df['Low'], df['Close'], length=14)
        if adx_df is None or adx_df.empty: return None
        
        # Robust column search
        adx_col = next((c for c in adx_df.columns if c.startswith("ADX")), None)
        if not adx_col: return None
        
        df['ADX'] = adx_df[adx_col]
        df['RSI'] = ta.rsi(df['Close'], length=14)
        
        # Shift for anti-lookahead
        df['ADX_Prev'] = df['ADX'].shift(1)
        df['RSI_Prev'] = df['RSI'].shift(1)
        df.dropna(inplace=True)
        return df
    except: return None

def objective(trial, df):
    adx_thresh = trial.suggest_int("adx_trend", 20, 30)
    rsi_thresh = trial.suggest_int("rsi_trend", 45, 60)
    tp = trial.suggest_float("target", 0.10, 0.30)
    sl = trial.suggest_float("stop", 0.05, 0.10)

    opens = df['Open'].values
    highs = df['High'].values
    lows  = df['Low'].values
    closes = df['Close'].values
    adx_p = df['ADX_Prev'].values
    rsi_p = df['RSI_Prev'].values

    balance = 1000.0
    pos = 0
    entry = 0.0
    
    for i in range(len(df)):
        if pos > 0:
            stop_px = entry * (1 - sl)
            take_px = entry * (1 + tp)
            
            # Simulated Execution using High/Low
            if lows[i] <= stop_px:
                balance = pos * min(opens[i], stop_px); pos = 0; continue
            if highs[i] >= take_px:
                balance = pos * max(opens[i], take_px); pos = 0; continue
            
            # Trend Reversal Safety
            if rsi_p[i] < 40:
                balance = pos * opens[i]; pos = 0; continue
        else:
            if adx_p[i] > adx_thresh and rsi_p[i] > rsi_thresh:
                entry = opens[i]; pos = balance / entry
    
    final = balance if pos == 0 else pos * closes[-1]
    return (final - 1000.0) / 1000.0

def optimize_stock(symbol, broker):
    print(f"🕵️ Tuning {symbol}...")
    raw = get_stock_data(symbol)
    if raw is None or len(raw) < 100: return
    df = precompute_indicators(raw)
    if df is None: return

    try:
        sampler = optuna.samplers.TPESampler(seed=42)
        study = optuna.create_study(direction="maximize", sampler=sampler)
        study.optimize(partial(objective, df=df), n_trials=100)
        
        is_holding = broker.is_holding(symbol)
        save_strategy(symbol, study.best_params, is_holding is not None)
        print(f"✅ Tuned {symbol}: {study.best_value:.2%}")
        del df; del raw; del study; gc.collect()
    except Exception as e: print(f"⚠️ Error {symbol}: {e}")

if __name__ == "__main__":
    init_db()
    broker = Broker()
    print("🚀 Starting AI Parameter Tuning...")
    for t in TICKERS: optimize_stock(t, broker)