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
from src.strategies.stop_manager import update_trailing_stops  # IMPORTED

job_lock = threading.Lock()
DB_PATH = os.getenv("DB_PATH", "/app/data/trading.db")

def get_active_strategies():
    try:
        with sqlite3.connect(DB_PATH, timeout=10) as conn:
            conn.execute("PRAGMA busy_timeout=5000;")
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
    try:
        if not os.path.exists(DB_PATH): return
        with sqlite3.connect(DB_PATH, timeout=10) as conn:
            c = conn.cursor()
            c.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='strategies'")
            if c.fetchone()[0] == 0: return 

            c.execute("SELECT count(*) FROM strategies")
            if c.fetchone()[0] == 0:
                print("⚡ DB is empty. Seeding from config/settings.yaml...")
                config_path = "/app/config/settings.yaml"
                if os.path.exists(config_path):
                    with open(config_path, "r") as f:
                        config = yaml.safe_load(f)
                    for symbol, settings in config.get('strategies', {}).items():
                        if settings.get('enabled'):
                            params = {
                                "rsi_length": settings.get('rsi_length', 14),
                                "rsi_panic_threshold": settings.get('rsi_panic_threshold', 30),
                                "qty": settings.get('qty', 1),
                                "take_profit_pct": 0.50, # Set to 50% for Moonshot
                                "stop_loss_pct": 0.10,   # Set to 10% Initial
                                "timeframe": settings.get('timeframe', '2h')
                            }
                            c.execute("INSERT INTO strategies (symbol, strategy_type, params, is_active) VALUES (?, ?, ?, 1)", 
                                      (symbol, 'rsi_panic', json.dumps(params)))
                    conn.commit()
                    print("✅ Seeding complete.")
    except Exception as e:
        print(f"Seeding Error: {e}")

def job(broker):
    if not job_lock.acquire(blocking=False):
        print("Skipping cycle: Previous cycle still running.")
        return

    try:
        vacuum_db() 
        strategies = get_active_strategies()
        
        # 1. RUN ENTRY LOGIC
        for symbol, config in strategies.items():
            if config['type'] == 'rsi_panic':
                 check_signal(symbol, config['params'], broker)
        
        # 2. RUN EXIT LOGIC (ACTIVE MANAGER)
        # This manages the trailing stops for all open positions
        update_trailing_stops(broker)
                 
    except Exception as e:
        print(f"Cycle Error: {e}")
    finally:
        job_lock.release()

def main():
    print("🤖 Algo Trading Bot Starting...")
    init_db()
    seed_db_from_yaml()
    try:
        broker = AlpacaClient()
    except Exception as e:
        print(f"CRITICAL: Could not connect to Broker: {e}")
        return

    job(broker)
    schedule.every(1).minutes.do(job, broker=broker)
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    main()