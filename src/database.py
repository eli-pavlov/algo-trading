import sqlite3
import os
import json
from datetime import datetime

DB_PATH = os.getenv("DB_PATH", "data/trading.db")

def init_db():
    """Initializes the database and ensures all tables exist."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS strategies (symbol TEXT PRIMARY KEY, params TEXT, is_active INTEGER)")
        conn.execute("CREATE TABLE IF NOT EXISTS system_status (key TEXT PRIMARY KEY, value TEXT)")
        conn.execute("CREATE TABLE IF NOT EXISTS manual_orders (id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, qty REAL, side TEXT, type TEXT, status TEXT DEFAULT 'PENDING')")

        # TCA Table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS trade_execution (
                order_id TEXT PRIMARY KEY,
                symbol TEXT, side TEXT, qty REAL, order_type TEXT,
                snapshot_price REAL, fill_price REAL, slippage_pct REAL,
                submitted_at TEXT, filled_at TEXT,
                api_latency_ms REAL, fill_latency_ms REAL, status TEXT
            )
        """)
        
        conn.execute("INSERT OR IGNORE INTO system_status (key, value) VALUES ('engine_running', '1')")
        conn.execute("INSERT OR IGNORE INTO system_status (key, value) VALUES ('api_health', 'Unknown')")
        conn.commit()

def update_status(key, value):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("INSERT OR REPLACE INTO system_status (key, value) VALUES (?, ?)", (key, str(value)))

def get_status(key, default="0"):
    with sqlite3.connect(DB_PATH) as conn:
        try:
            res = conn.execute("SELECT value FROM system_status WHERE key = ?", (key,)).fetchone()
            return res[0] if res else default
        except: return default

def save_strategy(symbol, params, is_active):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("INSERT OR REPLACE INTO strategies (symbol, params, is_active) VALUES (?, ?, ?)", 
                     (symbol, json.dumps(params), 1 if is_active else 0))

def delete_strategy(symbol):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM strategies WHERE symbol = ?", (symbol,))

def get_strategies():
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute("SELECT symbol, params FROM strategies").fetchall()
        return {row[0]: json.loads(row[1]) for row in rows}

def get_pending_manual_orders():
    with sqlite3.connect(DB_PATH) as conn:
        return conn.execute("SELECT id, symbol, qty, side, type FROM manual_orders WHERE status='PENDING'").fetchall()

def update_manual_order_status(o_id, status):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("UPDATE manual_orders SET status=? WHERE id=?", (status, o_id))

def log_trade_attempt(order_id, symbol, side, qty, type, snapshot_px, latency_ms):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT OR IGNORE INTO trade_execution 
            (order_id, symbol, side, qty, order_type, snapshot_price, submitted_at, api_latency_ms, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'NEW')
        """, (str(order_id), symbol, side, float(qty), type, float(snapshot_px), 
              datetime.utcnow().isoformat(), float(latency_ms)))

def update_trade_fill(order_id, fill_px, filled_at):
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT snapshot_price, side, submitted_at FROM trade_execution WHERE order_id=?", (order_id,)).fetchone()
        if row:
            snap_px, side, sub_at_str = row
            slip_pct = 0.0
            if snap_px and fill_px:
                diff = fill_px - snap_px
                slip_pct = (diff / snap_px) * 100
                if side == 'sell': slip_pct *= -1
            
            fill_ms = 0.0
            try:
                t_sub = datetime.fromisoformat(sub_at_str)
                t_fill = datetime.fromisoformat(filled_at.replace("Z", "+00:00"))
                if t_sub.tzinfo is None:
                    from datetime import timezone
                    t_sub = t_sub.replace(tzinfo=timezone.utc)
                fill_ms = (t_fill - t_sub).total_seconds() * 1000
            except: pass

            conn.execute("""
                UPDATE trade_execution 
                SET fill_price=?, filled_at=?, slippage_pct=?, fill_latency_ms=?, status='FILLED'
                WHERE order_id=?
            """, (float(fill_px), str(filled_at), float(slip_pct), float(fill_ms), order_id))