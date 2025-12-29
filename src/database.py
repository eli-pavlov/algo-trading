import sqlite3
import os
import json

DB_PATH = os.getenv("DB_PATH", "data/trading.db")

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        # Strategy storage
        conn.execute("CREATE TABLE IF NOT EXISTS strategies (symbol TEXT PRIMARY KEY, params TEXT, is_active INTEGER)")
        # Equity tracking
        conn.execute("CREATE TABLE IF NOT EXISTS equity_history (timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, balance REAL)")
        # NEW: System state (Engine Toggle, API Health)
        conn.execute("CREATE TABLE IF NOT EXISTS system_status (key TEXT PRIMARY KEY, value TEXT)")
        # NEW: Manual Command Queue
        conn.execute("CREATE TABLE IF NOT EXISTS manual_orders (id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, qty REAL, side TEXT, type TEXT, status TEXT DEFAULT 'PENDING')")
        
        # Default state
        conn.execute("INSERT OR IGNORE INTO system_status (key, value) VALUES ('engine_running', '1')")
        conn.execute("INSERT OR IGNORE INTO system_status (key, value) VALUES ('api_health', 'Unknown')")

def update_status(key, value):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("INSERT OR REPLACE INTO system_status (key, value) VALUES (?, ?)", (key, str(value)))

def get_status(key, default="0"):
    with sqlite3.connect(DB_PATH) as conn:
        res = conn.execute("SELECT value FROM system_status WHERE key = ?", (key,)).fetchone()
        return res[0] if res else default

# ... keep existing save_strategy and get_strategies functions ...