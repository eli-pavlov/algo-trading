import time
import schedule
import yaml
import os
from dotenv import load_dotenv
from src.utils.logger import setup_logger
from src.brokers.alpaca_api import AlpacaClient
from src.strategies.rsi_panic import check_signal

# Load Environment and Logging
load_dotenv()
logger = setup_logger("Main")

CONFIG_PATH = "config/settings.yaml"

def load_config():
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)

def job():
    try:
        config = load_config()
        broker = AlpacaClient() # Re-init to ensure fresh connection/auth check

        logger.info("--- Starting Analysis Cycle ---")
        
        strategies = config.get("strategies", {})
        for symbol, settings in strategies.items():
            if settings.get("enabled"):
                check_signal(symbol, settings, broker)
        
        logger.info("--- Cycle Complete ---")

    except Exception as e:
        logger.error(f"Critical Error in Job Cycle: {e}")

def main():
    logger.info("🤖 Algo Trading Bot Starting...")
    logger.info(f"Mode: {os.getenv('TRADING_MODE', 'UNKNOWN')}")
    
    # Run once immediately on startup
    job()

    # Schedule subsequent runs
    config = load_config()
    interval = config['system']['update_interval_minutes']
    schedule.every(interval).minutes.do(job)

    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    main()