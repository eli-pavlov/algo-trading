import schedule
import time
import os
import yfinance as yf
# Using absolute imports for Docker compatibility
from src.database import init_db, get_strategies
from src.broker import Broker

def daily_summary():
    """Triggered at market close to send P&L to Slack."""
    broker = Broker()
    try:
        stats = broker.get_account_stats()
        perf = broker.get_performance_summary()
        broker.send_webhook_report(stats, title="📊 END OF DAY STATS")
        broker.send_webhook_report(perf, title="📈 PERFORMANCE SUMMARY")
    except Exception as e:
        print(f"Error generating daily summary: {e}")

def heart_beat():
    """1-minute pulse to check signals and execute trades."""
    with open("/tmp/heartbeat", "w") as f:
        f.write(str(time.time()))

    broker = Broker()
    if not broker.api.get_clock().is_open:
        return

    strategies = get_strategies()
    for sym, p in strategies.items():
        if not broker.is_holding(sym):
            df = yf.download(sym, period="5d", interval="1h", progress=False)
            if df.empty:
                continue

            # Indicators logic
            adx = df.ta.adx().iloc[-1]['ADX_14']
            rsi = df.ta.rsi().iloc[-1]

            if adx > p.get('adx_trend', 25) and rsi > p.get('rsi_trend', 50):
                broker.buy_bracket(
                    sym, 
                    qty=1, 
                    tp_pct=p['target'], 
                    sl_pct=p['stop']
                )

if __name__ == "__main__":
    init_db()
    print("🚀 Algo-Trading Machine Active...")

    schedule.every(1).minutes.do(heart_beat)
    # Set to 16:00 (4 PM) EST or your preferred time
    schedule.every().day.at("21:00").do(daily_summary)

    while True:
        schedule.run_pending()
        time.sleep(1)