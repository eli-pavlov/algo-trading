import schedule
import time
import os
import sqlite3
import json
import yfinance as yf
from ta.trend import ADXIndicator
from ta.momentum import RSIIndicator
from src.database import init_db, get_strategies, get_status, update_status, DB_PATH
from src.broker import Broker

def process_manual_queue(broker):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            orders = conn.execute(
                "SELECT id, symbol, qty, side, type FROM manual_orders WHERE status='PENDING'"
            ).fetchall()
            for o in orders:
                o_id, sym, qty, side, o_type = o
                try:
                    broker.api.submit_order(symbol=sym, qty=qty, side=side, type=o_type, time_in_force='gtc')
                    conn.execute("UPDATE manual_orders SET status='COMPLETED' WHERE id=?", (o_id,))
                except Exception:
                    conn.execute("UPDATE manual_orders SET status='FAILED' WHERE id=?", (o_id,))
    except Exception as e:
        print(f"Error in manual queue: {e}")

def daily_summary():
    broker = Broker()
    try:
        stats = broker.get_account_stats()
        perf = broker.get_performance_summary()
        broker.send_webhook_report(stats, title="📊 END OF DAY STATS")
        broker.send_webhook_report(perf, title="📈 PERFORMANCE SUMMARY")
    except Exception:
        pass

def heart_beat():
    with open("/tmp/heartbeat", "w") as f:
        f.write(str(time.time()))

    broker = Broker()
    try:
        clock = broker.api.get_clock()
        market_open = clock.is_open
        update_status("api_health", "🟢 ONLINE" if market_open else "🟡 MARKET CLOSED")
    except Exception:
        update_status("api_health", "🔴 API DISCONNECTED")
        return

    process_manual_queue(broker)

    if get_status("engine_running") == "0":
        return

    if market_open:
        strategies = get_strategies()
        # Calculate how many potential symbols we are tracking
        num_symbols = len(strategies) if len(strategies) > 0 else 1
        
        account = broker.api.get_account()
        total_equity = float(account.portfolio_value)
        cash_available = float(account.cash)
        
        # Equal-Weight Logic: Split total equity by number of tracked stocks
        target_usd_per_stock = total_equity / num_symbols

        for sym, p in strategies.items():
            df = yf.download(sym, period="5d", interval="1h", progress=False)
            if df.empty:
                continue

            adx_gen = ADXIndicator(high=df['High'], low=df['Low'], close=df['Close'], window=14)
            rsi_gen = RSIIndicator(close=df['Close'], window=14)
            curr_rsi = rsi_gen.rsi().iloc[-1]
            curr_adx = adx_gen.adx().iloc[-1]

            is_holding = broker.is_holding(sym)

            # 🟢 BUY LOGIC
            if not is_holding:
                if curr_adx > p.get('adx_trend', 25) and curr_rsi > p.get('rsi_trend', 50):
                    current_price = float(broker.api.get_latest_trade(sym).price)
                    
                    # Spend the target amount, limited by actual cash on hand
                    allowed_spend = min(target_usd_per_stock, cash_available)
                    qty_to_buy = int(allowed_spend / current_price)

                    if qty_to_buy > 0:
                        broker.buy_bracket(sym, qty_to_buy, p['target'], p['stop'])
                        cash_available -= (qty_to_buy * current_price)

            # 🔴 EXIT LOGIC (Per Symbol)
            elif is_holding:
                # If RSI falls below 40, we exit the WHOLE position for this symbol
                if curr_rsi < 40:
                    print(f"📉 Exit Signal for {sym}: RSI {curr_rsi:.2f} < 40")
                    broker.sell_all(sym)

if __name__ == "__main__":
    init_db()
    print("🚀 Algo-Trading Heart Started...")
    schedule.every(1).minutes.do(heart_beat)
    schedule.every().day.at("21:00").do(daily_summary)
    heart_beat()
    while True:
        schedule.run_pending()
        time.sleep(1)