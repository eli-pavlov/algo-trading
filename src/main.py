import schedule, time, os
from database import init_db, get_strategies
from broker import Broker
import pandas_ta as ta
import yfinance as yf

def heart_beat():
    broker = Broker()
    # 1. Healthcheck Update: Touch a file so Docker knows we are alive
    with open("/tmp/heartbeat", "w") as f:
        f.write(str(time.time()))

    if not broker.api.get_clock().is_open: 
        return
    
    # ... Trading Logic ...

if __name__ == "__main__":
    init_db()
    schedule.every(1).minutes.do(heart_beat)
    while True:
        schedule.run_pending()
        time.sleep(1)