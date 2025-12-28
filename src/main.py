import time
import schedule
import threading
import json
import sqlite3
from src.brokers.alpaca_api import AlpacaClient
from src.utils.database import init_db, vacuum_db

job_lock = threading.Lock()

def get_active_strategies():
    """Reads configuration from DB instead of YAML"""
    conn = sqlite3.connect("/app/data/trading.db")
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

def job(broker):
    # 1. Locking (Efficiency Proposal A)
    if not job_lock.acquire(blocking=False):
        print("Skipping cycle: Previous cycle still running.")
        return

    try:
        # 2. DB Maintenance (New Requirement)
        vacuum_db() 

        # 3. Dynamic Config
        strategies = get_active_strategies()
        
        for symbol, config in strategies.items():
            # 4. Strategy Dispatcher
            if config['type'] == 'rsi_panic':
                 # Pass specific params per stock
                 check_signal(symbol, config['params'], broker)
            elif config['type'] == 'macd_cross':
                 check_macd(symbol, config['params'], broker)
                 
    except Exception as e:
        print(f"Cycle Error: {e}")
    finally:
        job_lock.release()

def main():
    init_db()
    # 5. Singleton Client (Efficiency Proposal A)
    broker = AlpacaClient() 
    
    schedule.every(1).minutes.do(job, broker=broker)
    
    while True:
        schedule.run_pending()
        time.sleep(1)