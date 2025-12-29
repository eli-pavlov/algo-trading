import schedule, time, os
from src.database import init_db, get_strategies
from src.broker import Broker
import pandas_ta as ta
import yfinance as yf

def heart_beat():
    # 1. Healthcheck file for Docker monitoring
    with open("/tmp/heartbeat", "w") as f:
        f.write(str(time.time()))

    broker = Broker()
    if not broker.api.get_clock().is_open:
        return

    strategies = get_strategies()
    for sym, p in strategies.items():
        pos = broker.is_holding(sym)
        
        if not pos:
            # Simple Trigger Example
            df = yf.download(sym, period="5d", interval="1h", progress=False)
            adx = df.ta.adx().iloc[-1]['ADX_14']
            if adx > p.get('adx_trend', 25):
                broker.buy_bracket(sym, 1, p['target'], p['stop'])

if __name__ == "__main__":
    init_db()
    print("🚀 Algo-Trading Heart Started...")
    schedule.every(1).minutes.do(heart_beat)
    while True:
        schedule.run_pending()
        time.sleep(1)