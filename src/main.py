import schedule
import time
import os
import subprocess
import numpy as np
import yfinance as yf
import pandas as pd
import pytz
from ta.trend import ADXIndicator
from ta.momentum import RSIIndicator
from src.database import init_db, get_strategies, get_status, update_status, get_pending_manual_orders, update_manual_order_status
from src.broker import Broker
# --- NEW IMPORT: Trigger the report ---
from src.notifications import send_trade_notification

# Set Market Timezone to New York
MARKET_TZ = "America/New_York"

def process_manual_queue(broker):
    try:
        orders = get_pending_manual_orders()
        for o in orders:
            o_id, sym, qty, side, o_type = o
            try:
                broker.submit_manual_order(sym, qty, side, o_type)
                update_manual_order_status(o_id, 'COMPLETED')
                
                # --- TRIGGER: Manual Trade Executed ---
                print(f"✅ Manual Order {sym} Completed. Sending Report...")
                send_trade_notification()
                
            except Exception:
                update_manual_order_status(o_id, 'FAILED')
    except Exception as e:
        print(f"Error in manual queue: {e}")

def daily_summary():
    broker = Broker()
    try:
        stats = broker.get_account_stats()
        perf = broker.get_portfolio_history_stats()
        print(f"Daily Stats: {stats} | Performance: {perf}")
    except: pass

def run_reoptimization():
    print("🧠 Starting Weekly Re-Optimization...")
    try:
        subprocess.Popen(["python", "src/tuner.py"])
        print("✅ Optimization started in background")
    except Exception as e:
        print(f"❌ Failed to start optimizer: {e}")

def heart_beat():
    with open("/tmp/heartbeat", "w") as f:
        f.write(str(time.time()))

    broker = Broker()
    try:
        msg = broker.get_market_clock()
        market_open = "🟢" in msg
        update_status("api_health", msg)
    except:
        update_status("api_health", "🔴 API DISCONNECTED")
        return

    # Check for manual orders regardless of market status (queued)
    process_manual_queue(broker)

    if get_status("engine_running") == "0": return

    if market_open:
        strategies = get_strategies()
        num_symbols = len(strategies) if len(strategies) > 0 else 1

        try:
            account = broker.api.get_account()
            total_equity = float(account.portfolio_value)
            cash_available = float(account.cash)
        except: return

        target_usd_per_stock = total_equity / num_symbols

        for sym, p in strategies.items():
            # 1. Download (Shape Fix + Threadless)
            df = yf.download(sym, period="5d", interval="1h", progress=False, threads=False)
            if df.empty: continue

            # --- CRITICAL FIX: Flatten 2D Data ---
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            
            for c in ["High", "Low", "Close"]:
                if c in df.columns:
                    s = df[c]
                    if isinstance(s, pd.DataFrame): s = s.iloc[:, 0]
                    df[c] = pd.Series(np.asarray(s).reshape(-1), index=df.index)
            # -------------------------------------

            # 2. Indicators
            try:
                adx_gen = ADXIndicator(high=df['High'], low=df['Low'], close=df['Close'], window=14)
                rsi_gen = RSIIndicator(close=df['Close'], window=14)
                curr_rsi = rsi_gen.rsi().iloc[-1]
                curr_adx = adx_gen.adx().iloc[-1]
            except: continue

            # 3. Execution
            is_holding = broker.is_holding(sym)
            has_pending = broker.has_open_order(sym)

            if not is_holding and not has_pending:
                if curr_adx > p.get('adx_trend', 25) and curr_rsi > p.get('rsi_trend', 50):
                    try:
                        current_price = float(broker.api.get_latest_trade(sym).price)
                        allowed_spend = min(target_usd_per_stock, cash_available)
                        qty = int(allowed_spend / current_price)
                        if qty > 0:
                            print(f"🚀 BUY SIGNAL: {sym}")
                            broker.buy_bracket(sym, qty, p['target'], p['stop'])
                            cash_available -= (qty * current_price)
                            
                            # --- TRIGGER: Auto Buy Executed ---
                            send_trade_notification()
                            
                    except: pass

            elif is_holding:
                if curr_rsi < 40:
                    broker.sell_all(sym)
                    
                    # --- TRIGGER: Auto Sell Executed ---
                    print(f"📉 SELL SIGNAL: {sym}")
                    send_trade_notification()

if __name__ == "__main__":
    init_db()
    print("🚀 Algo-Trading Heart Started...")
    schedule.every(1).minutes.do(heart_beat)
    schedule.every().day.at("21:00").do(daily_summary)
    schedule.every().sunday.at("04:00").do(run_reoptimization)
    heart_beat()
    while True:
        schedule.run_pending()
        time.sleep(1)