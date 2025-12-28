import sqlite3
import json
import time
import os
from src.utils.logger import setup_logger

logger = setup_logger("Database")
DB_PATH = os.getenv("DB_PATH", "/app/data/trading.db")

def _connect():
    """Creates a connection with optimal settings for concurrency"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10) # Higher timeout for safety
    # Enable WAL mode for concurrency (Dashboard reading while Bot writes)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn

def init_db():
    try:
        conn = _connect()
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
        logger.info("Database initialized successfully (WAL mode).")
    except Exception as e:
        logger.error(f"DB Init Failed: {e}")

def vacuum_db(max_size_mb=500):
    try:
        if not os.path.exists(DB_PATH):
            return

        file_size = os.path.getsize(DB_PATH) / (1024 * 1024) 
        if file_size > (max_size_mb * 0.9): 
            logger.warning(f"DB is large ({file_size:.2f}MB). Cleaning old data...")
            conn = _connect()
            c = conn.cursor()
            c.execute("DELETE FROM market_cache") 
            c.execute("VACUUM") 
            conn.commit()
            conn.close()
    except Exception as e:
        logger.error(f"Vacuum Failed: {e}")

def log_trade(symbol, side, qty, price, strategy="Unknown", client_order_id=None):
    try:
        conn = _connect()
        c = conn.cursor()
        c.execute("""INSERT INTO trades 
                     (symbol, side, qty, price_filled, strategy, client_order_id) 
                     VALUES (?, ?, ?, ?, ?, ?)""",
                  (symbol, side, qty, price, strategy, client_order_id))
        conn.commit()
        conn.close()
        logger.info(f"Trade logged to DB: {side} {symbol} @ {price}")
    except sqlite3.IntegrityError:
        logger.warning(f"Duplicate trade detected for ID {client_order_id}, skipping log.")
    except Exception as e:
        logger.error(f"Failed to log trade: {e}")