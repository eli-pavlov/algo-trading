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

job_lock = threading.Lock()
DB_PATH = os.getenv("DB_PATH", "/app/data/trading.db")

def get_active_strategies():
    """Reads configuration from DB instead of YAML"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT symbol, strategy_type, params FROM strategies WHERE is_active=1")
        rows = c.fetchall()
        conn.close()
        
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
    """Populates DB from settings.yaml if DB is empty"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        # Check if table exists and is empty
        c.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='strategies'")
        if c.fetchone()[0] == 0:
            # Init DB will create tables, but let's be safe and poll strategy count
            return 

        c.execute("SELECT count(*) FROM strategies")
        if c.fetchone()[0] == 0:
            print("⚡ DB is empty. Seeding from config/settings.yaml...")
            config_path = "/app/config/settings.yaml"
            if os.path.exists(config_path):
                with open(config_path, "r") as f:
                    config = yaml.safe_load(f)
                
                for symbol, settings in config.get('strategies', {}).items():
                    if settings.get('enabled'):
                        # Convert yaml settings to the JSON params format expected by DB
                        params = {
                            "rsi_length": settings.get('rsi_length', 14),
                            "rsi_panic_threshold": settings.get('rsi_panic_threshold', 30),
                            "qty": settings.get('qty', 1),
                            "take_profit_pct": settings.get('take_profit_pct', 0.05),
                            "stop_loss_pct": settings.get('stop_loss_pct', 0.02),
                            "timeframe": settings.get('timeframe', '2h')
                        }
                        c.execute("INSERT INTO strategies VALUES (?, ?, ?, 1)", 
                                  (symbol, 'rsi_panic', json.dumps(params)))
                conn.commit()
                print("✅ Seeding complete.")
            else:
                print("⚠️ Config file not found for seeding.")
        conn.close()
    except Exception as e:
        print(f"Seeding Error: {e}")

def job(broker):
    # 1. Locking (Efficiency)
    if not job_lock.acquire(blocking=False):
        print("Skipping cycle: Previous cycle still running.")
        return

    try:
        # 2. DB Maintenance
        vacuum_db() 

        # 3. Dynamic Config
        strategies = get_active_strategies()
        
        if not strategies:
            print("No active strategies found in DB.")

        for symbol, config in strategies.items():
            # 4. Strategy Dispatcher
            if config['type'] == 'rsi_panic':
                 check_signal(symbol, config['params'], broker)
            # Add other strategies here (e.g. macd)
                 
    except Exception as e:
        print(f"Cycle Error: {e}")
    finally:
        job_lock.release()

def main():
    print("🤖 Algo Trading Bot Starting...")
    
    # Initialize Infrastructure
    init_db()
    seed_db_from_yaml()
    
    # Singleton Client
    try:
        broker = AlpacaClient()
    except Exception as e:
        print(f"CRITICAL: Could not connect to Broker: {e}")
        return

    # Schedule Jobs
    schedule.every(1).minutes.do(job, broker=broker)
    
    # Run loop
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    main()