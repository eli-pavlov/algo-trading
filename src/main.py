import schedule
import time
import os
from src.database import init_db, get_strategies
from src.broker import Broker
import yfinance as yf

def daily_summary():
    """Sends the P&L report you used on your ARM server to Slack."""
    broker = Broker()
    stats = broker.get_account_stats()
    perf = broker.get_performance_summary()
    
    broker.send_webhook_report(stats, title="📊 END OF DAY STATS")
    broker.send_webhook_report(perf, title="📈 PERFORMANCE SUMMARY")

def heart_beat():
    """The 1-minute execution loop."""
    # Docker Healthcheck touch
    with open("/tmp/heartbeat", "w") as f:
        f.write(str(time.time()))

    broker = Broker()
    
    # Check if Market is Open
    if not broker.api.get_clock().is_open:
        return

    # Process each active strategy from the Database
    strategies = get_strategies()
    for sym, p in strategies.items():
        if not broker.is_holding(sym):
            # Fetch fresh 1h data
            df = yf.download(sym, period="5d", interval="1h", progress=False)
            if df.empty:
                continue

            # Indicators (via pandas_ta extension)
            adx = df.ta.adx().iloc[-1]['ADX_14']
            rsi = df.ta.rsi().iloc[-1]

            # Strategy Logic (Trend Following)
            if adx > p.get('adx_trend', 25) and rsi > p.get('rsi_trend', 50):
                # Entry with SL and TP from the Optimizer
                broker.buy_bracket(
                    sym, 
                    qty=1, 
                    tp_pct=p['target'], 
                    sl_pct=p['stop']
                )

if __name__ == "__main__":
    # 1. Initialize Memory
    init_db()
    print("🚀 Algo-Trading Machine Active...")

    # 2. Schedule the Heart Beat (Every Minute)
    schedule.every(1).minutes.do(heart_beat)

    # 3. Schedule the Daily Report (e.g., 4:00 PM EST / 21:00 UTC)
    # Adjust this time based on your local server clock
    schedule.every().day.at("21:00").do(daily_summary)

    # 4. Infinite Loop
    while True:
        schedule.run_pending()
        time.sleep(1)