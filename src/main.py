import schedule
import time
import os
import sqlite3
import json
import numpy as np
import yfinance as yf
import pandas as pd
import pytz  # NEW: For timezone handling
from ta.trend import ADXIndicator
from ta.momentum import RSIIndicator
from src.database import init_db, get_strategies, get_status, update_status, DB_PATH
from src.broker import Broker

# Set Market Timezone
MARKET_TZ = "America/New_York"

def process_manual_queue(broker):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            orders = conn.execute(
                "SELECT id, symbol, qty, side, type FROM manual_orders WHERE status='PENDING'"
            ).fetchall()
            for o in orders:
                o_id, sym, qty, side, o_type = o
                try:
                    broker.submit_manual_order(sym, qty, side, o_type)
                    conn.execute("UPDATE manual_orders SET status='COMPLETED' WHERE id=?", (o_id,))
                except Exception:
                    conn.execute("UPDATE manual_orders SET status='FAILED' WHERE id=?", (o_id,))
    except Exception as e:
        print(f"Error in manual queue: {e}")


def daily_summary():
    broker = Broker()
    try:
        stats = broker.get_account_stats()
        perf = broker.get_portfolio_history_stats()
        print(f"Daily Stats: {stats} | Performance: {perf}")
    except Exception:
        pass


def heart_beat():
    # Health signal for Docker
    with open("/tmp/heartbeat", "w") as f:
        f.write(str(time.time()))

    broker = Broker()
    try:
        msg = broker.get_market_clock()
        market_open = "🟢" in msg
        update_status("api_health", msg)
    except Exception:
        update_status("api_health", "🔴 API DISCONNECTED")
        return

    process_manual_queue(broker)

    if get_status("engine_running") == "0":
        return

    if market_open:
        strategies = get_strategies()
        num_symbols = len(strategies) if len(strategies) > 0 else 1

        try:
            account = broker.api.get_account()
            total_equity = float(account.portfolio_value)
            cash_available = float(account.cash)
        except:
            return

        # Equal-Weight Logic
        target_usd_per_stock = total_equity / num_symbols

        for sym, p in strategies.items():
            # 1. Download Data (Threadless for ARM stability)
            df = yf.download(sym, period="5d", interval="1h", progress=False, threads=False)

            if df.empty:
                continue

            # --- ROBUST SHAPE FIX (From DeepSeek Scanner) ---
            # 1. Handle MultiIndex Columns
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            
            # 2. Force 1D Series for critical columns (The scanner's "magic fix")
            # This prevents "ValueError: Data must be 1-dimensional" crashes
            for c in ["High", "Low", "Close"]:
                if c in df.columns:
                    s = df[c]
                    if isinstance(s, pd.DataFrame):
                        s = s.iloc[:, 0]
                    # Reshape ensures it's strictly a 1D array, then rebuild Series
                    df[c] = pd.Series(np.asarray(s).reshape(-1), index=df.index)
            # ------------------------------------------------

            # 2. Calculate Indicators
            try:
                adx_gen = ADXIndicator(high=df['High'], low=df['Low'], close=df['Close'], window=14)
                rsi_gen = RSIIndicator(close=df['Close'], window=14)

                curr_rsi = rsi_gen.rsi().iloc[-1]
                curr_adx = adx_gen.adx().iloc[-1]
            except Exception as e:
                print(f"⚠️ Indiccalc error {sym}: {e}")
                continue

            is_holding = broker.is_holding(sym)
            has_pending = broker.has_open_order(sym)

            # 3. Trade Logic
            # 🟢 BUY
            if not is_holding and not has_pending:
                if curr_adx > p.get('adx_trend', 25) and curr_rsi > p.get('rsi_trend', 50):
                    try:
                        current_price = float(broker.api.get_latest_trade(sym).price)
                        allowed_spend = min(target_usd_per_stock, cash_available)
                        qty_to_buy = int(allowed_spend / current_price)

                        if qty_to_buy > 0:
                            print(f"🚀 BUY SIGNAL: {sym} @ ${current_price}")
                            broker.buy_bracket(sym, qty_to_buy, p['target'], p['stop'])
                            cash_available -= (qty_to_buy * current_price)
                    except Exception as e:
                        print(f"❌ Buy failed {sym}: {e}")

            # 🔴 SELL (Exit Signal - Safety Net)
            elif is_holding:
                if curr_rsi < 40:
                    print(f"📉 EXIT SIGNAL: {sym} RSI {curr_rsi:.2f} < 40")
                    broker.sell_all(sym)


if __name__ == "__main__":
    init_db()
    print("🚀 Algo-Trading Heart Started...")
    
    # Schedule Heartbeat every minute
    schedule.every(1).minutes.do(heart_beat)
    
    # Schedule Summary at 21:00 New York Time (Market Close + 5h usually, but safer to pin)
    # Note: 'schedule' library uses system time. 
    # To truly align with NY, we simply check time inside the job or use a timezone-aware scheduler.
    # For simplicity here, we keep 21:00 but rely on the broker checks for market open/close status.
    schedule.every().day.at("21:00").do(daily_summary)

    # Run once immediately on startup
    heart_beat()

    while True:
        schedule.run_pending()
        time.sleep(1)