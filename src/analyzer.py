import os
import yfinance as yf
import pandas_ta_classic as ta
import optuna
import urllib3
import pandas as pd
from src.database import save_strategy, init_db
from src.broker import Broker

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TICKERS = ['HOOD', 'AMD', 'AI', 'CVNA', 'PLTR']

def objective(trial, df):
    """Optuna objective to maximize profit in a 1-year backtest."""
    adx_threshold = trial.suggest_int("adx_trend", 15, 35)
    rsi_threshold = trial.suggest_int("rsi_trend", 40, 65)
    tp = trial.suggest_float("target", 0.10, 0.40)
    sl = trial.suggest_float("stop", 0.03, 0.15)

    df_copy = df.copy()
    
    # Calculate ADX safely
    # pandas-ta-classic requires explicit high, low, close
    adx_df = ta.adx(df_copy['High'], df_copy['Low'], df_copy['Close'], length=14)
    
    if adx_df is None or adx_df.empty:
        return -100 # Penalize if indicator fails

    # Merge ADX back into main dataframe
    df_copy['ADX'] = adx_df.iloc[:, 0] # Use the first column of the ADX result
    df_copy['RSI'] = ta.rsi(df_copy['Close'], length=14)
    
    # Drop rows where indicators are NaN (the warm-up period)
    df_copy = df_copy.dropna(subset=['ADX', 'RSI'])

    score, in_pos, entry = 0, False, 0
    for i in range(1, len(df_copy)):
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
    # 1. Download data
    df = yf.download(symbol, period="1y", interval="1h", progress=False)

    if df.empty:
        print(f"❌ No data for {symbol}")
        return

    # 2. Flatten MultiIndex columns if necessary (new yfinance behavior)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    # 3. Optimize
    study = optuna.create_study(direction="maximize")
    study.optimize(lambda trial: objective(trial, df), n_trials=20)
    
    print(f"✅ Best for {symbol}: {study.best_params}")
    
    # 4. Save
    is_holding = broker.is_holding(symbol)
    save_strategy(symbol, study.best_params, is_holding is not None)

if __name__ == "__main__":
    init_db()
    broker = Broker()
    for t in TICKERS:
        try:
            optimize_stock(t, broker)
        except Exception as e:
            print(f"⚠️ Error on {t}: {e}")