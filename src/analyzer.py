import yfinance as yf
import pandas_ta as ta
import optuna
from src.database import save_strategy
from broker import Broker

TICKERS = ['HOOD', 'AMD', 'AI', 'CVNA', 'PLTR']

def optimize_stock(symbol):
    df = yf.download(symbol, period="1y", interval="1h")
    # ... (Insert the Optuna Logic from previous steps here) ...
    # Simplified placeholder for brevity:
    best_params = {"adx_trend": 25, "rsi_trend": 50, "stop": 0.05, "target": 0.20}
    
    broker = Broker()
    save_strategy(symbol, best_params, broker.is_holding(symbol))

if __name__ == "__main__":
    for t in TICKERS: optimize_stock(t)