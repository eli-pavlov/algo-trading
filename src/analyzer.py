import yfinance as yf
import pandas_ta as ta  # This now points to pandas-ta-classic
import optuna
import os
from src.database import save_strategy
from src.broker import Broker

# Configuration for optimization
TICKERS = ['HOOD', 'AMD', 'AI', 'CVNA', 'PLTR']


def objective(trial, df):
    """
    Optuna objective function: Simulates trading with different 
    parameters to maximize profit.
    """
    # Parameter Search Space
    adx_threshold = trial.suggest_int("adx_trend", 15, 35)
    rsi_threshold = trial.suggest_int("rsi_trend", 40, 65)
    tp = trial.suggest_float("target", 0.10, 0.40)
    sl = trial.suggest_float("stop", 0.03, 0.15)

    # Calculate indicators using pandas_ta extensions
    # We use the copy to avoid modifying the original dataframe
    df_copy = df.copy()
    adx_df = df_copy.ta.adx(length=14)
    
    # Handle different column names produced by pandas_ta
    adx_col = [col for col in adx_df.columns if 'ADX' in col][0]
    df_copy['ADX'] = adx_df[adx_col]
    df_copy['RSI'] = df_copy.ta.rsi(length=14)

    # Fast Backtest Simulation
    score = 0
    in_pos = False
    entry = 0

    for i in range(1, len(df_copy)):
        price = df_copy['Close'].iloc[i]
        curr_adx = df_copy['ADX'].iloc[i]
        curr_rsi = df_copy['RSI'].iloc[i]

        if not in_pos:
            if curr_adx > adx_threshold and curr_rsi > rsi_threshold:
                entry = price
                in_pos = True
        else:
            if price >= entry * (1 + tp):
                score += tp
                in_pos = False
            elif price <= entry * (1 - sl):
                score -= sl
                in_pos = False

    return score


def optimize_stock(symbol):
    print(f"🧠 Optimizing intelligence for: {symbol}")
    # Download 1 year of data for deep learning
    df = yf.download(symbol, period="1y", interval="1h", progress=False)

    if df.empty:
        print(f"⚠️ No data for {symbol}")
        return

    # Create Optuna study
    study = optuna.create_study(direction="maximize")
    study.optimize(lambda trial: objective(trial, df), n_trials=30)

    best_params = study.best_params
    print(f"✅ Optimization complete. Best settings: {best_params}")

    # Save to SQLite so main.py can pick them up
    broker = Broker()
    save_strategy(symbol, best_params, broker.is_holding(symbol))


if __name__ == "__main__":
    # Ensure database is ready
    from src.database import init_db
    init_db()
    
    for ticker in TICKERS:
        try:
            optimize_stock(ticker)
        except Exception as e:
            print(f"❌ Failed to optimize {ticker}: {e}")