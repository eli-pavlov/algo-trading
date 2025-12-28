import time
import schedule
import threading
import json
import sqlite3
import yaml
import os
from src.brokers.alpaca_api import AlpacaClient
from src.utils.database import init_db, vacuum_db
from src.strategies.rsi_panic import check_signal
from src.strategies.stop_manager import update_trailing_stops

# Global Lock to prevent overlapping jobs if API is slow
job_lock = threading.Lock()

DB_PATH = os.getenv("DB_PATH", "/app/data/trading.db")

def get_active_strategies():
    """
    Fetches all enabled strategies from the local database.
    """
    try:
        # Improved connection logic with timeouts
        with sqlite3.connect(DB_PATH, timeout=10) as conn:
            conn.execute("PRAGMA busy_timeout=5000;") # Wait up to 5s if DB is locked
            c = conn.cursor()
            c.execute("SELECT symbol, strategy_type, params FROM strategies WHERE is_active=1")
            rows = c.fetchall()
        
        strategies = {}
        for r in rows:
            strategies[r[0]] = {
                "type": r[1],
                "params": json.loads(r[2])
            }
        return strategies
    except Exception as e:
        print(f"Error reading DB: {e}")
        return {}

def seed_db_from_yaml():
    """
    On startup, populates the DB with settings from config/settings.yaml
    """
    try:
        if not os.path.exists(DB_PATH): return

        with sqlite3.connect(DB_PATH, timeout=10) as conn:
            c = conn.cursor()
            # Check if table exists
            c.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='strategies'")
            if c.fetchone()[0] == 0: return 

            # Check if table is empty
            c.execute("SELECT count(*) FROM strategies")
            if c.fetchone()[0] == 0:
                print("⚡ DB is empty. Seeding from config/settings.yaml...")
                config_path = "/app/config/settings.yaml"
                
                if os.path.exists(config_path):
                    with open(config_path, "r") as f:
                        config = yaml.safe_load(f)
                    
                    for symbol, settings in config.get('strategies', {}).items():
                        if settings.get('enabled'):
                            # Prepare params with defaults
                            params = {
                                "rsi_length": settings.get('rsi_length', 14),
                                "rsi_panic_threshold": settings.get('rsi_panic_threshold', 30),
                                "qty": settings.get('qty', 1),
                                # Moonshot Settings: Wide TP, Tight Stop
                                "take_profit_pct": 0.50, 
                                "stop_loss_pct": 0.10,   
                                "timeframe": settings.get('timeframe', '2h')
                            }
                            c.execute("""
                                INSERT INTO strategies (symbol, strategy_type, params, is_active) 
                                VALUES (?, ?, ?, 1)
                            """, (symbol, 'rsi_panic', json.dumps(params)))
                    
                    conn.commit()
                    print("✅ Seeding complete.")
    except Exception as e:
        print(f"Seeding Error: {e}")

def job(broker):
    """
    The Main Loop. Runs every minute.
    """
    # 1. Concurrency Check
    if not job_lock.acquire(blocking=False):
        print("⚠️ Skipping cycle: Previous cycle still running (API Slow?).")
        return

    try:
        # 2. Global Market Guard (The "Gatekeeper")
        # We check this ONCE per minute to save API calls.
        try:
            clock = broker.api.get_clock()
            if not clock.is_open:
                # Calculate time until open for a helpful log message
                # (Optional optimization: sleep longer if hours away)
                print(f"💤 Market Closed. Next Open: {clock.next_open}. Sleeping...")
                return # EXIT JOB. Do not run strategies.
        except Exception as e:
            print(f"⚠️ Alpaca Clock Error: {e}. Skipping cycle for safety.")
            return

        # 3. Maintenance
        vacuum_db() 
        strategies = get_active_strategies()
        
        if not strategies:
            print("No active strategies found.")

        # 4. Run Entry Logic (The Sniper)
        for symbol, config in strategies.items():
            if config['type'] == 'rsi_panic':
                 # We pass the broker. check_signal will handle data fetching.
                 check_signal(symbol, config['params'], broker)
        
        # 5. Run Exit Logic (The Manager)
        # This checks all open positions and updates trailing stops
        update_trailing_stops(broker)
                 
    except Exception as e:
        print(f"❌ Cycle Error: {e}")
    finally:
        # Always release the lock, even if error occurs
        job_lock.release()

def main():
    print("🤖 Algo Trading Bot Starting...")
    
    # Initialize Infrastructure
    init_db()
    seed_db_from_yaml()
    
    # Connect to Broker
    try:
        broker = AlpacaClient()
        print(f"✅ Connected to Alpaca ({os.getenv('TRADING_MODE', 'PAPER')})")
    except Exception as e:
        print(f"💀 CRITICAL: Could not connect to Broker: {e}")
        return

    # Run the first job immediately (don't wait 1 minute)
    print("🚀 Running initial cycle...")
    job(broker)

    # Schedule the loop
    # Every 1 minute is the "Sensible Level" for Alpaca Limits.
    schedule.every(1).minutes.do(job, broker=broker)
    
    print("⏱️  Scheduler active. Ctrl+C to exit.")
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    main()