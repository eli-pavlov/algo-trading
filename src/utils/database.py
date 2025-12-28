import sqlite3
import json
import time
import os
from src.utils.logger import setup_logger

logger = setup_logger("Database")
# Use getenv so it matches the other files' logic
DB_PATH = os.getenv("DB_PATH", "/app/data/trading.db")

def init_db():
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # 1. Configuration Table
        c.execute('''CREATE TABLE IF NOT EXISTS strategies
                     (symbol TEXT PRIMARY KEY,
                      strategy_type TEXT,
                      params TEXT, 
                      is_active INTEGER DEFAULT 1)''')

        # 2. Trades Table
        c.execute('''CREATE TABLE IF NOT EXISTS trades
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                      symbol TEXT,
                      side TEXT,
                      qty REAL,
                      price_requested REAL,
                      price_filled REAL,
                      slippage REAL,
                      strategy TEXT,
                      client_order_id TEXT UNIQUE)''')

        # 3. Market Cache
        c.execute('''CREATE TABLE IF NOT EXISTS market_cache
                     (symbol TEXT,
                      data_blob BLOB,
                      updated_at REAL,
                      PRIMARY KEY (symbol))''')

        conn.commit()
        conn.close()
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.error(f"DB Init Failed: {e}")

def vacuum_db(max_size_mb=500):
    """
    Auto-cleaning logic: Removes old logs/cache if DB gets too big.
    """
    try:
        if not os.path.exists(DB_PATH):
            return

        file_size = os.path.getsize(DB_PATH) / (1024 * 1024) # Size in MB
        if file_size > (max_size_mb * 0.9): # 90% capacity warning
            logger.warning(f"DB is large ({file_size:.2f}MB). Cleaning old data...")
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("DELETE FROM market_cache") 
            c.execute("VACUUM") 
            conn.commit()
            conn.close()
    except Exception as e:
        logger.error(f"Vacuum Failed: {e}")

# --- THIS WAS MISSING ---
def log_trade(symbol, side, qty, price, strategy="Unknown"):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT INTO trades (symbol, side, qty, price_filled, strategy) VALUES (?, ?, ?, ?, ?)",
                  (symbol, side, qty, price, strategy))
        conn.commit()
        conn.close()
        logger.info(f"Trade logged to DB: {side} {symbol} @ {price}")
    except Exception as e:
        logger.error(f"Failed to log trade: {e}")