import sqlite3, os, json

# Use env var for path to ensure it works in Docker volumes
DB_PATH = os.getenv("DB_PATH", "data/trading.db")

def init_db():
    # Ensure directory exists
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS strategies (symbol TEXT PRIMARY KEY, params TEXT, is_active INTEGER)")
        # Added a table to track performance for the dashboard
        conn.execute("CREATE TABLE IF NOT EXISTS equity_history (timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, balance REAL)")