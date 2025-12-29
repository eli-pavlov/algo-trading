import os
import yfinance as yf
import pandas_ta_classic as ta
import optuna
import urllib3
import pandas as pd
import numpy as np
import gc
import shutil
from functools import partial
from src.database import save_strategy, init_db
from src.broker import Broker

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Tuner operates on the specific list of stocks you want to trade
TICKERS = ['HOOD', 'AMD', 'AI', 'CVNA', 'PLTR']

def get_stock_data(symbol):
    """
    Downloads and cleans data.
    - Fixed: auto_adjust=False (keeps raw OHLC)
    - Fixed: Robust flattening of MultiIndex
    """
    try:
        # Threads=False for ARM/Docker stability
        df = yf.download(symbol, period="1y", interval="1h", 
                         progress=False, threads=False, auto_adjust=False)
        
        if df.empty: return None

        # 1. Fix MultiIndex Columns (Ticker -> Price)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # 2. Fix 2D Array Issues (The "Shape" Fix)
        for c in ["Open", "High", "Low", "Close"]:
            if c in df.columns:
                s = df[c]
                if isinstance(s, pd.DataFrame): s = s.iloc[:, 0]
                df[c] = pd.Series(np.asarray(s).reshape(-1), index=df.index)

        return df
    except Exception as e:
        print(f"❌ Download failed for {symbol}: {e}")
        return None

def precompute_indicators(df):
    """
    Calculates indicators ONCE before optimization loop.
    - Fixed: Robust ADX column selection
    """
    df = df.copy()
    try:
        # ADX (Directional Movement)
        adx_df = ta.adx(df['High'], df['Low'], df['Close'], length=14)
        if adx_df is None or adx_df.empty: return None
        
        # Find the correct column (ADX_14 or similar)
        adx_col = next((c for c in adx_df.columns if c.startswith("ADX")), None)
        if not adx_col: return None
        
        df['ADX'] = adx_df[adx_col]
        
        # RSI
        df['RSI'] = ta.rsi(df['Close'], length=14)
        
        # Shift indicators so Row 'i' sees the metrics from 'i-1' (No Lookahead)
        df['ADX_Prev'] = df['ADX'].shift(1)
        df['RSI_Prev'] = df['RSI'].shift(1)
        
        df.dropna(inplace=True)
        return df
    except Exception:
        return None

def objective(trial, df):
    """
    Simulates trading with REALISTIC constraints.
    - No Lookahead: Decision made on (i-1), Execution on Open(i)
    - Intra-bar Exits: Check Low vs SL and High vs TP
    """
    # 1. Suggest Parameters
    adx_thresh = trial.suggest_int("adx_trend", 20, 30)
    rsi_thresh = trial.suggest_int("rsi_trend", 45, 60)
    tp_pct = trial.suggest_float("target", 0.10, 0.30)
    sl_pct = trial.suggest_float("stop", 0.05, 0.10)

    # Convert columns to numpy arrays for massive speed boost
    opens = df['Open'].values
    highs = df['High'].values
    lows  = df['Low'].values
    closes = df['Close'].values
    adx_prev = df['ADX_Prev'].values
    rsi_prev = df['RSI_Prev'].values

    # Simulation State
    balance = 1000.0  # Virtual starting cash
    position = 0      # 0 = flat, >0 = shares
    entry_price = 0.0
    
    # 2. Fast Vectorized-Style Loop
    for i in range(len(df)):
        # EXIT LOGIC (If we have a position)
        if position > 0:
            # Check Stop Loss First (Conservative assumption: SL hits before TP)
            stop_price = entry_price * (1 - sl_pct)
            take_price = entry_price * (1 + tp_pct)
            
            # Did we hit SL?
            if lows[i] <= stop_price:
                # We assume we got filled at the stop price (or Open if it gapped down)
                exit_fill = min(opens[i], stop_price)
                balance = position * exit_fill
                position = 0
                continue # Trade over
            
            # Did we hit TP?
            if highs[i] >= take_price:
                # We assume we got filled at target (or Open if it gapped up)
                exit_fill = max(opens[i], take_price)
                balance = position * exit_fill
                position = 0
                continue # Trade over
                
            # Trend Reversal Exit (RSI < 40 safety net)
            # We use the previous closed RSI to decide to sell at Open[i]
            if rsi_prev[i] < 40:
                balance = position * opens[i]
                position = 0
                continue

        # ENTRY LOGIC (If we are flat)
        else:
            # Decision based on PREVIOUS candle (adx_prev, rsi_prev)
            # Execution happens at CURRENT Open
            if adx_prev[i] > adx_thresh and rsi_prev[i] > rsi_thresh:
                entry_price = opens[i]
                position = balance / entry_price # All-in

    # Final MTM (Mark to Market) if still holding
    final_equity = balance if position == 0 else position * closes[-1]
    
    # Return Percentage Return as the Score
    return (final_equity - 1000.0) / 1000.0

def optimize_stock(symbol, broker):
    print(f"🕵️ Tuning {symbol}...")

    # 1. Get Data
    raw_df = get_stock_data(symbol)
    if raw_df is None or len(raw_df) < 100:
        print(f"❌ Insufficient data for {symbol}")
        return

    # 2. Precompute Indicators (Huge Speedup)
    df = precompute_indicators(raw_df)
    if df is None:
        print(f"❌ Indicator error for {symbol}")
        return

    # 3. Optimize
    try:
        # Seed=42 ensures that if you run it twice, you get the same 'best' params
        sampler = optuna.samplers.TPESampler(seed=42)
        study = optuna.create_study(direction="maximize", sampler=sampler)

        # Bind the precomputed DF to the objective
        optimization_func = partial(objective, df=df)
        
        # 100 Trials is fast now because we precomputed math
        study.optimize(optimization_func, n_trials=100) 

        print(f"✅ Best for {symbol}: {study.best_params} (Score: {study.best_value:.2%})")

        is_holding = broker.is_holding(symbol)
        save_strategy(symbol, study.best_params, is_holding is not None)

        # Cleanup
        del df
        del raw_df
        del study
        gc.collect()

    except Exception as e:
        print(f"⚠️ Optimization error on {symbol}: {e}")

if __name__ == "__main__":
    init_db()
    broker = Broker()
    
    # Note: We removed the aggressive cache deletion logic.
    # Only delete cache manually if you suspect data corruption.
    
    print("🚀 Starting AI Parameter Tuning...")
    for t in TICKERS:
        optimize_stock(t, broker)