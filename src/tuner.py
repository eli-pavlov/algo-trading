import os
import yfinance as yf
import pandas_ta_classic as ta
import optuna
import urllib3
import pandas as pd
import gc
import shutil
from functools import partial
from src.database import save_strategy, init_db
from src.broker import Broker

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TICKERS = ['HOOD', 'AMD', 'AI', 'CVNA', 'PLTR']


def objective(trial, df):
    # Reduced search space for stability
    adx_threshold = trial.suggest_int("adx_trend", 20, 30)
    rsi_threshold = trial.suggest_int("rsi_trend", 45, 60)
    tp = trial.suggest_float("target", 0.10, 0.30)
    sl = trial.suggest_float("stop", 0.05, 0.10)

    df_copy = df.copy()

    # Check for valid data length for indicators
    if len(df_copy) < 50:
        return -100

    # Calculate ADX safely
    try:
        adx_df = ta.adx(df_copy['High'], df_copy['Low'], df_copy['Close'], length=14)
        if adx_df is None or adx_df.empty:
            return -100

        # Use position-based indexing (safer than name-based)
        df_copy['ADX'] = adx_df.iloc[:, 0]
        df_copy['RSI'] = ta.rsi(df_copy['Close'], length=14)
        df_copy.dropna(subset=['ADX', 'RSI'], inplace=True)
    except Exception:
        return -100

    score, in_pos, entry = 0, False, 0
    # Vectorized calculation is faster but iterating is fine for logic clarity
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


def get_stock_data(symbol):
    """Helper to fetch and clean data, isolated for linter safety."""
    try:
        df = yf.download(symbol, period="1y", interval="1h", progress=False, threads=False)
        if df.empty:
            return None

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        return df
    except Exception as e:
        print(f"❌ Download failed for {symbol}: {e}")
        return None


def optimize_stock(symbol, broker):
    print(f"🕵️ Analyzing {symbol}...")

    # 1. Get Data
    df = get_stock_data(symbol)

    if df is None or df.empty:
        print(f"❌ No data for {symbol}")
        return

    # 2. Optimize
    try:
        study = optuna.create_study(direction="maximize")

        # Use partial to bind df explicitly, which satisfies the linter
        optimization_func = partial(objective, df=df)
        study.optimize(optimization_func, n_trials=5)

        print(f"✅ Best for {symbol}: {study.best_params}")

        is_holding = broker.is_holding(symbol)
        save_strategy(symbol, study.best_params, is_holding is not None)

        # Cleanup
        del df
        del study
        gc.collect()

    except Exception as e:
        print(f"⚠️ Optimization error on {symbol}: {e}")


if __name__ == "__main__":
    init_db()

    # Clear yfinance cache to prevent corruption errors
    cache_dir = os.path.expanduser("~/.cache/yfinance")
    if os.path.exists(cache_dir):
        shutil.rmtree(cache_dir)

    broker = Broker()
    for t in TICKERS:
        optimize_stock(t, broker)