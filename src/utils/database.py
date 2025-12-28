import sqlite3
import json
import time
import os  # <--- WAS MISSING
from src.utils.logger import setup_logger

logger = setup_logger("Database")
DB_PATH = "/app/data/trading.db" # Updated path for Docker volume

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # 1. Configuration Table (The "Brain")
    # Stores: symbol='TSLA', strategy='rsi_panic', params='{"threshold": 7, "qty": 5}', active=1
    c.execute('''CREATE TABLE IF NOT EXISTS strategies
                 (symbol TEXT PRIMARY KEY,
                  strategy_type TEXT,
                  params TEXT, 
                  is_active INTEGER DEFAULT 1)''')

    # 2. Trades Table (Performance tracking)
    # Added: entry_id (client_order_id), fill_price, slippage
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

    # 3. Market Cache (To save API calls)
    c.execute('''CREATE TABLE IF NOT EXISTS market_cache
                 (symbol TEXT,
                  data_blob BLOB,
                  updated_at REAL,
                  PRIMARY KEY (symbol))''')

    conn.commit()
    conn.close()

def vacuum_db(max_size_mb=500):
    """
    Auto-cleaning logic: Removes old logs/cache if DB gets too big.
    """
    file_size = os.path.getsize(DB_PATH) / (1024 * 1024) # Size in MB
    if file_size > (max_size_mb * 0.9): # 90% capacity warning
        logger.warning(f"DB is large ({file_size:.2f}MB). Cleaning old data...")
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        # Delete trades older than 90 days (optional) or just clear cache
        c.execute("DELETE FROM market_cache") 
        c.execute("VACUUM") # Compresses the DB file
        conn.commit()
        conn.close()