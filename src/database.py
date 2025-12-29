import sqlite3
import os
import json

DB_PATH = os.getenv("DB_PATH", "data/trading.db")

def init_db():
    """Initializes the database and ensures all tables exist."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        # 1. Strategies Table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS strategies 
            (symbol TEXT PRIMARY KEY, params TEXT, is_active INTEGER)
        """)
        # 2. Status Table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS system_status 
            (key TEXT PRIMARY KEY, value TEXT)
        """)
        # 3. Manual Orders Table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS manual_orders 
            (id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, qty REAL, 
             side TEXT, type TEXT, status TEXT DEFAULT 'PENDING')
        """)
        
        # Insert Default Values
        conn.execute("INSERT OR IGNORE INTO system_status (key, value) VALUES ('engine_running', '1')")
        conn.execute("INSERT OR IGNORE INTO system_status (key, value) VALUES ('api_health', 'Unknown')")
        conn.commit()

def update_status(key, value):
    init_db()  # Defensive check
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("INSERT OR REPLACE INTO system_status (key, value) VALUES (?, ?)", (key, str(value)))

def get_status(key, default="0"):
    init_db()  # Defensive check
    with sqlite3.connect(DB_PATH) as conn:
        try:
            res = conn.execute("SELECT value FROM system_status WHERE key = ?", (key,)).fetchone()
            return res[0] if res else default
        except sqlite3.OperationalError:
            return default

def save_strategy(symbol, params, is_active):
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO strategies (symbol, params, is_active) VALUES (?, ?, ?)",
            (symbol, json.dumps(params), 1 if is_active else 0)
        )

# --- NEW FUNCTION ---
def delete_strategy(symbol):
    """Removes a strategy from the database. Stops future buys."""
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM strategies WHERE symbol = ?", (symbol,))
# --------------------

def get_strategies():
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute("SELECT symbol, params FROM strategies").fetchall()
        return {row[0]: json.loads(row[1]) for row in rows}