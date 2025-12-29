import sqlite3
import os
import json
from datetime import datetime

DB_PATH = os.getenv("DB_PATH", "data/trading.db")

def init_db():
    """Initializes the database and ensures all tables exist."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        # ... (Existing tables: strategies, system_status, manual_orders) ...
        conn.execute("""
            CREATE TABLE IF NOT EXISTS strategies 
            (symbol TEXT PRIMARY KEY, params TEXT, is_active INTEGER)
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS system_status 
            (key TEXT PRIMARY KEY, value TEXT)
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS manual_orders 
            (id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, qty REAL, 
             side TEXT, type TEXT, status TEXT DEFAULT 'PENDING')
        """)

        # --- NEW TABLE: Transaction Cost Analysis (TCA) ---
        # Stores the price we WANTED (Snapshot) vs the price we GOT (Fill)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS trade_execution (
                order_id TEXT PRIMARY KEY,
                symbol TEXT,
                side TEXT,
                qty REAL,
                order_type TEXT,
                snapshot_price REAL,  -- Price at moment of logic
                fill_price REAL,      -- Actual execution price
                slippage_pct REAL,    -- (Fill - Snapshot) / Snapshot
                submitted_at TEXT,
                filled_at TEXT,
                status TEXT
            )
        """)
        
        # Insert Default Values
        conn.execute("INSERT OR IGNORE INTO system_status (key, value) VALUES ('engine_running', '1')")
        conn.execute("INSERT OR IGNORE INTO system_status (key, value) VALUES ('api_health', 'Unknown')")
        conn.commit()

# ... (Keep existing update_status, get_status, save_strategy, delete_strategy, get_strategies) ...
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

def delete_strategy(symbol):
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM strategies WHERE symbol = ?", (symbol,))

def get_strategies():
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute("SELECT symbol, params FROM strategies").fetchall()
        return {row[0]: json.loads(row[1]) for row in rows}

# --- NEW TCA FUNCTIONS ---
def log_trade_attempt(order_id, symbol, side, qty, type, snapshot_px):
    """Records the intent to trade before we know the result."""
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT OR IGNORE INTO trade_execution 
            (order_id, symbol, side, qty, order_type, snapshot_price, submitted_at, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'NEW')
        """, (str(order_id), symbol, side, float(qty), type, float(snapshot_px), datetime.utcnow().isoformat()))

def update_trade_fill(order_id, fill_px, filled_at):
    """Updates the record once Alpaca fills it, calculating slippage."""
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        # Get the original snapshot to calc slippage
        row = conn.execute("SELECT snapshot_price, side FROM trade_execution WHERE order_id=?", (order_id,)).fetchone()
        if row:
            snap_px, side = row
            if snap_px and fill_px:
                # Slippage logic: 
                # Buy: Positive if Fill > Snap (Bad)
                # Sell: Positive if Fill < Snap (Bad)
                diff = fill_px - snap_px
                slip_pct = (diff / snap_px) * 100
                
                # Invert for Sell side so Positive is always "Bad Slippage" (Cost)
                if side == 'sell':
                    slip_pct = slip_pct * -1
                
                conn.execute("""
                    UPDATE trade_execution 
                    SET fill_price=?, filled_at=?, slippage_pct=?, status='FILLED'
                    WHERE order_id=?
                """, (float(fill_px), str(filled_at), float(slip_pct), order_id))