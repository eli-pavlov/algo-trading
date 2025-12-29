import os
import yfinance as yf
import pandas_ta_classic as ta
import optuna
import urllib3
import pandas as pd
import gc
from src.database import save_strategy, init_db
from src.broker import Broker

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TICKERS = ['HOOD', 'AMD', 'AI', 'CVNA', 'PLTR']

def objective(trial, df):
    # Reduced search space slightly for speed/memory
    adx_threshold = trial.suggest_int("adx_trend", 15, 35)
    rsi_threshold = trial.suggest_int("rsi_trend", 40, 65)
    tp = trial.suggest_float("target", 0.10, 0.40)
    sl = trial.suggest_float("stop", 0.03, 0.15)

    df_copy = df.copy()
    
    # Calculate indicators
    adx_df = ta.adx(df_copy['High'], df_copy['Low'], df_copy['Close'], length=14)
    if adx_df is None or adx_df.empty:
        return -100

    df_copy['ADX'] = adx_df.iloc[:, 0]
    df_copy['RSI'] = ta.rsi(df_copy['Close'], length=14)
    df_copy.dropna(subset=['ADX', 'RSI'], inplace=True)

    score, in_pos, entry = 0, False, 0
    # Vectorized calculation is faster but iterating is fine for logic clarity
    # Keeping iteration to match your logic exactly
    for i in range(len(df_copy)):
        price = df_copy['Close'].iloc[i]
        curr_adx = df_copy['ADX'].iloc[i]
        curr_rsi = df_copy['RSI'].iloc[i]

        if not in_pos:
            if curr_adx > adx_threshold and curr_rsi > rsi_threshold:
                entry, in_pos = price, True
        else:
            if price >= entry * (1 + tp):
                score += tp
                in_pos = False
            elif price <= entry * (1 - sl):
                score -= sl
                in_pos = False
    return score

def optimize_stock(symbol, broker):
    print(f"🕵️ Analyzing {symbol}...")
    try:
        # Download data
        df = yf.download(symbol, period="1y", interval="1h", progress=False)
        
        if df.empty:
            print(f"❌ No data for {symbol}")
            return

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # Optimize (Reduced trials to prevent OOM)
        study = optuna.create_study(direction="maximize")
        study.optimize(lambda trial: objective(trial, df), n_trials=10)
        
        print(f"✅ Best for {symbol}: {study.best_params}")
        
        is_holding = broker.is_holding(symbol)
        save_strategy(symbol, study.best_params, is_holding is not None)
        
        # MEMORY CLEANUP: Critical for small instances
        del df
        del study
        gc.collect()
        
    except Exception as e:
        print(f"⚠️ Error on {symbol}: {e}")

if __name__ == "__main__":
    init_db()
    broker = Broker()
    for t in TICKERS:
        optimize_stock(t, broker)