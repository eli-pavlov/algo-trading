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
        # Download 1H data (we will aggregate this to 2H)
        df = yf.download(symbol, period="1y", interval="1h", progress=False, threads=False, auto_adjust=False)
        if df.empty:
            return None

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # Standardize columns
        for c in ["Open", "High", "Low", "Close", "Volume"]:
            if c in df.columns:
                s = df[c]
                if isinstance(s, pd.DataFrame):
                    s = s.iloc[:, 0]
                df[c] = pd.Series(np.asarray(s).reshape(-1), index=df.index)
        
        return df
    except Exception:
        return None


def precompute_indicators(df):
    df = df.copy()
    try:
        # --- CRITICAL: Resample to 2H to match Backtest Logic ---
        # Origin='start_day' ensures 9:30 candles align correctly (9:30-11:30)
        # We assume 9:30 market open.
        logic = {
            'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'
        }
        # offset='30min' helps align with NYSE 9:30 open if the index is clean, 
        # but origin='start_day' is usually safer for intraday chunks
        df_2h = df.resample('2h', origin='start_day').apply(logic).dropna()

        if df_2h.empty: return None

        # --- Calculate Indicators on the 2H Data ---
        adx_df = ta.adx(df_2h['High'], df_2h['Low'], df_2h['Close'], length=14)
        if adx_df is None or adx_df.empty:
            return None

        adx_col = next((c for c in adx_df.columns if c.startswith("ADX")), None)
        if not adx_col:
            return None

        df_2h['ADX'] = adx_df[adx_col]
        df_2h['RSI'] = ta.rsi(df_2h['Close'], length=14)

        # Shift for anti-lookahead (Decision based on PREVIOUS closed candle)
        df_2h['ADX_Prev'] = df_2h['ADX'].shift(1)
        df_2h['RSI_Prev'] = df_2h['RSI'].shift(1)
        df_2h.dropna(inplace=True)
        
        return df_2h
    except Exception as e:
        print(f"Indicator Error: {e}")
        return None


def objective(trial, df):
    # Parameter Search Space
    adx_thresh = trial.suggest_int("adx_trend", 20, 35)
    rsi_thresh = trial.suggest_int("rsi_trend", 40, 65)
    tp = trial.suggest_float("target", 0.05, 0.25)
    sl = trial.suggest_float("stop", 0.03, 0.12)

    opens = df['Open'].values
    highs = df['High'].values
    lows = df['Low'].values
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

            # Execution Logic (Simplified)
            if lows[i] <= stop_px:
                balance = pos * min(opens[i], stop_px)
                pos = 0
                continue
            if highs[i] >= take_px:
                balance = pos * max(opens[i], take_px)
                pos = 0
                continue
            
            # RSI Panic Exit (on 2H bar close)
            if rsi_p[i] < 35: 
                balance = pos * opens[i]
                pos = 0
                continue
        else:
            # Entry Logic
            if adx_p[i] > adx_thresh and rsi_p[i] > rsi_thresh:
                entry = opens[i]
                pos = balance / entry

    final = balance if pos == 0 else pos * closes[-1]
    return (final - 1000.0) / 1000.0


def optimize_stock(symbol, broker):
    print(f"🕵️ Tuning {symbol} (2H timeframe)...")
    raw = get_stock_data(symbol)
    if raw is None or len(raw) < 100:
        return
    
    # Precompute converts 1H raw -> 2H signals
    df = precompute_indicators(raw)
    if df is None:
        return

    try:
        sampler = optuna.samplers.TPESampler(seed=42)
        study = optuna.create_study(direction="maximize", sampler=sampler)
        study.optimize(partial(objective, df=df), n_trials=50) # 50 trials for speed

        is_holding = broker.is_holding(symbol)
        save_strategy(symbol, study.best_params, is_holding is not None)
        print(f"✅ Tuned {symbol}: {study.best_value:.2%} (Params: {study.best_params})")
        
        del df
        del raw
        del study
        gc.collect()
    except Exception as e:
        print(f"⚠️ Error {symbol}: {e}")


if __name__ == "__main__":
    init_db()
    broker = Broker()
    print("🚀 Starting AI Parameter Tuning (2H Candles)...")
    for t in TICKERS:
        optimize_stock(t, broker)