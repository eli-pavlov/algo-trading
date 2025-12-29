import schedule
import time
import os
import sqlite3
import yfinance as yf
from ta.trend import ADXIndicator
from ta.momentum import RSIIndicator
from src.database import init_db, get_strategies, get_status, update_status, DB_PATH
from src.broker import Broker

def process_manual_queue(broker):
    """
    Checks the database for manual orders sent from the Streamlit UI.
    This allows you to 'Buy/Sell' assets manually without stopping the bot.
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            # Find any orders that haven't been processed yet
            orders = conn.execute(
                "SELECT id, symbol, qty, side, type FROM manual_orders WHERE status='PENDING'"
            ).fetchall()
            
            for o in orders:
                o_id, sym, qty, side, o_type = o
                try:
                    print(f"🕹️ Executing Manual Order: {side} {qty} {sym}")
                    broker.api.submit_order(
                        symbol=sym,
                        qty=qty,
                        side=side,
                        type=o_type,
                        time_in_force='gtc'
                    )
                    conn.execute("UPDATE manual_orders SET status='COMPLETED' WHERE id=?", (o_id,))
                    broker.send_webhook_report(
                        {"Manual Order": "SUCCESS", "Details": f"{side} {qty} {sym}"}, 
                        title="🕹️ MANUAL OVERRIDE"
                    )
                except Exception as e:
                    print(f"❌ Manual Order Failed: {e}")
                    conn.execute("UPDATE manual_orders SET status='FAILED' WHERE id=?", (o_id,))
    except Exception as e:
        print(f"Error in manual queue: {e}")

def daily_summary():
    """Triggered at market close to send total portfolio value and P&L stats to Slack."""
    broker = Broker()
    try:
        stats = broker.get_account_stats()
        perf = broker.get_performance_summary()
        broker.send_webhook_report(stats, title="📊 END OF DAY STATS")
        broker.send_webhook_report(perf, title="📈 PERFORMANCE SUMMARY")
    except Exception as e:
        print(f"Error generating daily summary: {e}")

def heart_beat():
    """
    The main pulse of the trading engine.
    Checks API health, manual commands, and automated strategy signals.
    """
    # 1. Update Health Check for Docker
    with open("/tmp/heartbeat", "w") as f:
        f.write(str(time.time()))

    broker = Broker()
    
    # 2. Check API Health and Market Status
    try:
        clock = broker.api.get_clock()
        market_open = clock.is_open
        update_status("api_health", "🟢 ONLINE" if market_open else "🟡 MARKET CLOSED")
    except Exception:
        update_status("api_health", "🔴 API DISCONNECTED")
        return

    # 3. Always process manual orders, even if automated engine is 'OFF'
    process_manual_queue(broker)

    # 4. Check Engine Toggle (from UI)
    if get_status("engine_running") == "0":
        return

    # 5. Automated Strategy Execution (Only if Market is Open)
    if market_open:
        strategies = get_strategies()
        for sym, p in strategies.items():
            # Only trade if we don't already have a position
            if not broker.is_holding(sym):
                df = yf.download(sym, period="5d", interval="1h", progress=False)
                if df.empty:
                    continue

                # Indicators using the stable 'ta' library
                adx_gen = ADXIndicator(high=df['High'], low=df['Low'], close=df['Close'], window=14)
                rsi_gen = RSIIndicator(close=df['Close'], window=14)
                
                curr_adx = adx_gen.adx().iloc[-1]
                curr_rsi = rsi_gen.rsi().iloc[-1]

                # Strategy Check
                if curr_adx > p.get('adx_trend', 25) and curr_rsi > p.get('rsi_trend', 50):
                    broker.buy_bracket(
                        sym, 
                        qty=1, 
                        tp_pct=p['target'], 
                        sl_pct=p['stop']
                    )

if __name__ == "__main__":
    # Ensure database tables and initial states exist
    init_db()
    print("🚀 Algo-Trading Heart Started...")

    # Schedule the loop (Pulse every minute)
    schedule.every(1).minutes.do(heart_beat)
    
    # Schedule end-of-day reporting (Adjust time to your timezone)
    schedule.every().day.at("21:00").do(daily_summary)

    # Initial Run
    heart_beat()

    while True:
        schedule.run_pending()
        time.sleep(1)