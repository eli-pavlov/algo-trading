import sqlite3
import os
from src.utils.logger import setup_logger

logger = setup_logger("Database")
DB_PATH = "trading.db"

def init_db():
    """
    Creates the trades table if it doesn't exist.
    Called once at bot startup.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS trades
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                      symbol TEXT,
                      side TEXT,
                      qty REAL,
                      price REAL,
                      strategy TEXT)''')
        conn.commit()
        conn.close()
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.critical(f"Database Initialization Failed: {e}")

def log_trade(symbol, side, qty, price, strategy="Unknown"):
    """
    Inserts a trade record into the local database.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT INTO trades (symbol, side, qty, price, strategy) VALUES (?, ?, ?, ?, ?)",
                  (symbol, side, qty, price, strategy))
        conn.commit()
        conn.close()
        logger.info(f"Trade logged to DB: {side} {symbol} @ ${price}")
    except Exception as e:
        logger.error(f"Failed to log trade to DB: {e}")