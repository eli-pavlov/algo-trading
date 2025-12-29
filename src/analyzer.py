import yfinance as yf
import pandas_ta as ta
import optuna
from src.database import save_strategy
from src.broker import Broker

TICKERS = ['HOOD', 'AMD', 'AI', 'CVNA', 'PLTR']


def objective(trial, df):
    """
    Optuna objective function to simulate trades and find the 
    best RSI/ADX combination.
    """
    # Define the range of parameters to test
    adx_threshold = trial.suggest_int("adx_trend", 15, 35)
    rsi_threshold = trial.suggest_int("rsi_trend", 40, 65)
    tp = trial.suggest_float("target", 0.10, 0.40)
    sl = trial.suggest_float("stop", 0.03, 0.15)

    # Calculate indicators
    df_copy = df.copy()
    adx = df_copy.ta.adx()['ADX_14']
    rsi = df_copy.ta.rsi()

    # Simple Backtest Logic for Optimization
    score = 0
    in_position = False
    entry_price = 0

    for i in range(1, len(df_copy)):
        price = df_copy['Close'].iloc[i]

        if not in_position:
            if adx.iloc[i] > adx_threshold and rsi.iloc[i] > rsi_threshold:
                entry_price = price
                in_position = True
        else:
            # Check Exit Conditions
            if price >= entry_price * (1 + tp):
                score += tp
                in_position = False
            elif price <= entry_price * (1 - sl):
                score -= sl
                in_position = False

    return score


def optimize_stock(symbol):
    print(f"🕵️  Deep Analysis: {symbol}...")
    df = yf.download(symbol, period="1y", interval="1h", progress=False)

    if df.empty:
        print(f"❌ No data found for {symbol}")
        return

    # Create a study to find the best parameters
    study = optuna.create_study(direction="maximize")
    study.optimize(lambda trial: objective(trial, df), n_trials=50)

    best_params = study.best_params
    print(f"✅ Best Params for {symbol}: {best_params}")

    # Save to Database so main.py can use them
    broker = Broker()
    save_strategy(symbol, best_params, broker.is_holding(symbol))


if __name__ == "__main__":
    for t in TICKERS:
        try:
            optimize_stock(t)
        except Exception as e:
            print(f"⚠️ Error optimizing {t}: {e}")