import sqlite3
import os
import json

DB_PATH = os.getenv("DB_PATH", "data/trading.db")

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS strategies (symbol TEXT PRIMARY KEY, params TEXT, is_active INTEGER)")
        conn.execute("CREATE TABLE IF NOT EXISTS equity_history (timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, balance REAL)")

def save_strategy(symbol, params, is_holding):
    if is_holding:
        print(f"⚠️ {symbol} is currently active. Skipping rotation."); return
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("INSERT INTO strategies (symbol, params, is_active) VALUES (?,?,1) "
                     "ON CONFLICT(symbol) DO UPDATE SET params=excluded.params", 
                     (symbol, json.dumps(params)))

def get_strategies():
    with sqlite3.connect(DB_PATH) as conn:
        return {r[0]: json.loads(r[1]) for r in conn.execute("SELECT symbol, params FROM strategies WHERE is_active=1")}