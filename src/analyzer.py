import os
import yfinance as yf
import pandas_ta_classic as ta  # Correct import for the classic library
import optuna
import urllib3
from src.database import save_strategy, init_db
from src.broker import Broker

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TICKERS = ['HOOD', 'AMD', 'AI', 'CVNA', 'PLTR']

def objective(trial, df):
    adx_threshold = trial.suggest_int("adx_trend", 15, 35)
    rsi_threshold = trial.suggest_int("rsi_trend", 40, 65)
    tp = trial.suggest_float("target", 0.10, 0.40)
    sl = trial.suggest_float("stop", 0.03, 0.15)

    df_copy = df.copy()
    # Using the standard ta function call
    adx_df = ta.adx(df_copy['High'], df_copy['Low'], df_copy['Close'], length=14)
    adx_col = [col for col in adx_df.columns if 'ADX' in col][0]
    df_copy['ADX'] = adx_df[adx_col]
    df_copy['RSI'] = ta.rsi(df_copy['Close'], length=14)

    score, in_pos, entry = 0, False, 0
    for i in range(1, len(df_copy)):
        price = df_copy['Close'].iloc[i]
        if not in_pos:
            if df_copy['ADX'].iloc[i] > adx_threshold and df_copy['RSI'].iloc[i] > rsi_threshold:
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
    df = yf.download(symbol, period="1y", interval="1h", progress=False)
    if df.empty:
        print(f"❌ No data for {symbol}")
        return

    study = optuna.create_study(direction="maximize")
    study.optimize(lambda trial: objective(trial, df), n_trials=20)
    
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