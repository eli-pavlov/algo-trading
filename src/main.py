import schedule
import time
import threading
import numpy as np
import yfinance as yf
import pandas as pd
from ta.trend import ADXIndicator
from ta.momentum import RSIIndicator
from src.database import init_db, get_strategies, get_status, update_status, get_pending_manual_orders, update_manual_order_status
from src.broker import Broker
from src.notifications import send_trade_notification
from src.tuner import optimize_stock, TICKERS  # Import Tuner functions

# --- ASYNC TUNER LOGIC ---

def _run_tuner_job():
    """The actual heavy lifting function that runs in a background thread."""
    print("🧠 Starting Scheduled Weekly Tuning (Background Thread)...")
    try:
        # Create a dedicated broker instance for the tuner
        broker_tuner = Broker()
        for t in TICKERS:
            # This function (from src.tuner) already handles 2H resampling internally
            optimize_stock(t, broker_tuner)
        print("✅ Weekly Tuning Complete. New strategies saved to DB.")
    except Exception as e:
        print(f"❌ Tuning Thread Error: {e}")

def schedule_async_tuner():
    """Spawns the tuner thread so the main loop doesn't freeze."""
    print("⏳ Triggering Async Tuner...")
    t = threading.Thread(target=_run_tuner_job)
    t.start()

# --- TRADING LOGIC ---

def process_manual_queue(broker):
    try:
        orders = get_pending_manual_orders()
        for o in orders:
            o_id, sym, qty, side, o_type = o
            ok, msg = broker.submit_order(sym, qty, side, o_type)
            status = 'COMPLETED' if ok else 'FAILED'
            update_manual_order_status(o_id, status)
            if ok: send_trade_notification()
    except Exception as e:
        print(f"Manual Queue Error: {e}")

def heart_beat():
    # 1. Update Heartbeat File (for health checks)
    with open("/tmp/heartbeat", "w") as f: f.write(str(time.time()))

    broker = Broker()
    
    # 2. Check Connection
    ok, msg = broker.test_connection()
    update_status("api_health", msg)
    if not ok: return

    # 3. Manual Orders (Always run, even if engine is paused)
    process_manual_queue(broker)

    # 4. Check Engine Switch
    if get_status("engine_running") == "0": return

    # 5. Check Market Open
    if "Closed" in broker.get_market_clock(): return

    # 6. Strategy Logic
    strategies = get_strategies()
    if not strategies: return

    stats = broker.get_account_stats()
    cash = stats.get('Cash', 0.0)
    equity = stats.get('Equity', 0.0)
    # Simple allocation: Divide equity equally among active strategies
    target_per_stock = equity / len(strategies)

    for sym, p in strategies.items():
        # A. Get Data (1H Interval - 10 days is enough for indicators)
        df = yf.download(sym, period="10d", interval="1h", progress=False)
        if df.empty or len(df) < 14: continue
        
        # B. Clean & Resample to 2H (STRICT MATCH TO BACKTEST)
        try:
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            # Resample logic: 2H candles anchored to start of day (9:30, 11:30, etc.)
            logic = {'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}
            df_2h = df.resample('2h', origin='start_day').apply(logic).dropna()
            
            if len(df_2h) < 14: continue 

            # C. Calc Indicators on 2H Data
            # Note: We use iloc[-2] (The last COMPLETED candle) for signals.
            # This ensures we don't act on a "developing" candle that might repaint.
            # This matches the Backtest logic of "Close".
            
            close_series = df_2h['Close']
            high_series = df_2h['High']
            low_series = df_2h['Low']
            
            # Using iloc[-2] for "Confirmed" signal
            confirmed_rsi = RSIIndicator(close_series).rsi().iloc[-2]
            confirmed_adx = ADXIndicator(high_series, low_series, close_series).adx().iloc[-2]

        except Exception as e:
            print(f"Calc Error {sym}: {e}")
            continue

        # D. Check Positions
        pos = broker.is_holding(sym)

        # E. Execution Logic (Using Confirmed 2H Signals)
        if not pos:
            # ENTRY (Checks strictly against Tuned parameters)
            if confirmed_adx > p.get('adx_trend', 25) and confirmed_rsi > p.get('rsi_trend', 50):
                price = broker.get_latest_price(sym)
                if price > 0 and cash > price:
                    qty = int(min(cash, target_per_stock) / price)
                    if qty >= 1:
                        # CALCULATE BRACKET PRICES
                        tp_price = round(price * (1 + p['target']), 2)
                        sl_price = round(price * (1 - p['stop']), 2)
                        
                        # EXECUTE BRACKET (Market Buy + TP/SL Legs)
                        success, order_id = broker.submit_order_v2(
                            "market", 
                            symbol=sym, 
                            qty=qty, 
                            side="buy", 
                            take_profit={"limit_price": tp_price}, 
                            stop_loss={"stop_price": sl_price}
                        )
                        
                        if success:
                            send_trade_notification()
                            cash -= (qty * price) # Adjust local cash estimate to prevent double spend
        else:
            # EXIT (Panic / Strategy Exit)
            # If 2H RSI drops below 40 (Safety net), close it regardless of stops.
            if confirmed_rsi < 40:
                broker.close_position(sym)
                send_trade_notification()

if __name__ == "__main__":
    init_db()
    print("🚀 Algo-Trader (2H Strategy + Async Tuner) Starting...")
    
    # 1. TRADING SCHEDULE: Run the strategy check every minute
    schedule.every(1).minutes.do(heart_beat)
    
    # 2. TUNING SCHEDULE: Run optimization every Friday at 23:00 (11 PM)
    # This runs in a background thread so it won't block the trading loop.
    schedule.every().friday.at("23:00").do(schedule_async_tuner)
    
    while True:
        schedule.run_pending()
        time.sleep(1)