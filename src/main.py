import schedule
import time
import os
import sqlite3
import json
import subprocess
import numpy as np
import yfinance as yf
import pandas as pd
import pytz
from ta.trend import ADXIndicator
from ta.momentum import RSIIndicator
from src.database import init_db, get_strategies, get_status, update_status, DB_PATH
from src.broker import Broker

# Set Market Timezone to New York (Alpaca's Server Time)
MARKET_TZ = "America/New_York"

def process_manual_queue(broker):
    """Checks database for manual orders placed via Dashboard."""
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
    """Prints account stats. Can be extended to send Discord/Email alerts."""
    broker = Broker()
    try:
        stats = broker.get_account_stats()
        perf = broker.get_portfolio_history_stats()
        print(f"Daily Stats: {stats} | Performance: {perf}")
    except Exception:
        pass


def run_reoptimization():
    """Spawns the tuner process to refresh parameters."""
    print("🧠 Starting Weekly Re-Optimization...")
    try:
        # NOTE: Ensure you have renamed src/analyzer.py to src/tuner.py
        # If not, change this line to ["python", "src/analyzer.py"]
        subprocess.Popen(["python", "src/tuner.py"])
        print("✅ Optimization started in background")
    except Exception as e:
        print(f"❌ Failed to start optimizer: {e}")


def heart_beat():
    """The main logic loop. Runs every minute."""
    # 1. Health signal for Docker
    with open("/tmp/heartbeat", "w") as f:
        f.write(str(time.time()))

    broker = Broker()
    
    # 2. Check API Connection
    try:
        msg = broker.get_market_clock()
        market_open = "🟢" in msg
        update_status("api_health", msg)
    except Exception:
        update_status("api_health", "🔴 API DISCONNECTED")
        return

    # 3. Process Manual Orders (Works even if market is closed)
    process_manual_queue(broker)

    # 4. Check Engine Switch
    if get_status("engine_running") == "0":
        return

    # 5. Trading Logic (Only if Market Open)
    if market_open:
        strategies = get_strategies()
        num_symbols = len(strategies) if len(strategies) > 0 else 1

        try:
            account = broker.api.get_account()
            total_equity = float(account.portfolio_value)
            cash_available = float(account.cash)
        except Exception:
            return

        # Equal-Weight Allocation Logic
        target_usd_per_stock = total_equity / num_symbols

        for sym, p in strategies.items():
            # A. Download Data (Threadless for ARM/Docker stability)
            df = yf.download(sym, period="5d", interval="1h", progress=False, threads=False)

            if df.empty:
                continue

            # --- ROBUST SHAPE FIX (Prevents "Data must be 1-dimensional" crash) ---
            # 1. Handle MultiIndex Columns (e.g., Price -> Ticker)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            
            # 2. Force 1D Series for critical columns
            for c in ["High", "Low", "Close"]:
                if c in df.columns:
                    s = df[c]
                    if isinstance(s, pd.DataFrame):
                        s = s.iloc[:, 0]
                    # Reshape ensures it's strictly a 1D array, then rebuild Series
                    df[c] = pd.Series(np.asarray(s).reshape(-1), index=df.index)
            # ----------------------------------------------------------------------

            # B. Calculate Indicators
            try:
                adx_gen = ADXIndicator(high=df['High'], low=df['Low'], close=df['Close'], window=14)
                rsi_gen = RSIIndicator(close=df['Close'], window=14)

                curr_rsi = rsi_gen.rsi().iloc[-1]
                curr_adx = adx_gen.adx().iloc[-1]
            except Exception as e:
                print(f"⚠️ Indiccalc error {sym}: {e}")
                continue

            # C. Check Status
            is_holding = broker.is_holding(sym)
            has_pending = broker.has_open_order(sym)

            # D. Execution Logic
            
            # 🟢 BUY SIGNAL
            if not is_holding and not has_pending:
                # Retrieve strategy params with defaults
                adx_thresh = p.get('adx_trend', 25)
                rsi_thresh = p.get('rsi_trend', 50)
                
                if curr_adx > adx_thresh and curr_rsi > rsi_thresh:
                    try:
                        current_price = float(broker.api.get_latest_trade(sym).price)
                        allowed_spend = min(target_usd_per_stock, cash_available)
                        qty_to_buy = int(allowed_spend / current_price)

                        if qty_to_buy > 0:
                            print(f"🚀 BUY SIGNAL: {sym} @ ${current_price}")
                            broker.buy_bracket(sym, qty_to_buy, p['target'], p['stop'])
                            # Deduct cash locally to prevent overspending in same loop
                            cash_available -= (qty_to_buy * current_price)
                    except Exception as e:
                        print(f"❌ Buy failed {sym}: {e}")

            # 🔴 SELL SIGNAL (Safety Net)
            # Normal exits are handled by Alpaca Bracket Orders (TP/SL).
            # This is an extra safety check for "Trend Reversal".
            elif is_holding:
                if curr_rsi < 40:
                    print(f"📉 EXIT SIGNAL: {sym} RSI {curr_rsi:.2f} < 40")
                    broker.sell_all(sym)


if __name__ == "__main__":
    init_db()
    print("🚀 Algo-Trading Heart Started...")
    
    # 1. Trading Loop
    schedule.every(1).minutes.do(heart_beat)
    
    # 2. Daily Summary (aligned roughly to Market Close)
    schedule.every().day.at("21:00").do(daily_summary)

    # 3. Weekly Auto-Tuner (Sundays at 4 AM)
    schedule.every().sunday.at("04:00").do(run_reoptimization)

    # Run logic once immediately on startup
    heart_beat()

    while True:
        schedule.run_pending()
        time.sleep(1)