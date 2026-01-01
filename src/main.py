import schedule
import time
import threading
import numpy as np
import yfinance as yf
import pandas as pd
from ta.trend import ADXIndicator
from ta.momentum import RSIIndicator
from src.database import init_db, get_strategies, get_status, update_status, get_pending_manual_orders, update_manual_order_status, get_unfilled_executions, update_trade_fill
from src.broker import Broker
from src.notifications import send_trade_notification

# --- ASYNC TUNER LOGIC ---
def _run_tuner_job():
    print("🧠 Starting Scheduled Weekly Tuning...")
    try:
        from src.tuner import optimize_stock, TICKERS
        broker_tuner = Broker()
        for t in TICKERS:
            optimize_stock(t, broker_tuner)
        print("✅ Weekly Tuning Complete.")
    except Exception as e:
        print(f"❌ Tuning Error: {e}")

def schedule_async_tuner():
    t = threading.Thread(target=_run_tuner_job)
    t.start()

# --- NEW: SYNC LOGIC ---
def sync_order_statuses(broker):
    """Checks Alpaca for updates on orders we think are still 'NEW'."""
    try:
        pending = get_unfilled_executions() # Returns list of (order_id,)
        if not pending: return

        for (oid,) in pending:
            try:
                # Ask Alpaca for the latest status
                alpaca_order = broker.client.get_order_by_id(oid)
                
                if alpaca_order.status == 'filled':
                    # It filled! Update DB.
                    update_trade_fill(oid, float(alpaca_order.filled_avg_price), alpaca_order.filled_at, 'FILLED')
                    print(f"🔄 Synced Fill: {oid}")
                    
                elif alpaca_order.status in ['canceled', 'expired', 'rejected']:
                    # It died. Update DB.
                    update_trade_fill(oid, 0.0, str(datetime.utcnow()), alpaca_order.status.upper())
                    print(f"🔄 Synced Cancel: {oid}")
                    
            except Exception as e:
                # Order might not exist in Alpaca or network error
                pass
    except Exception as e:
        print(f"Sync Error: {e}")

# --- TRADING LOGIC ---
def process_manual_queue(broker):
    try:
        orders = get_pending_manual_orders()
        for o in orders:
            o_id, sym, qty, side, o_type = o
            ok, msg = broker.submit_order_v2(o_type, symbol=sym, qty=qty, side=side)
            status = 'COMPLETED' if ok else 'FAILED'
            update_manual_order_status(o_id, status)
    except Exception as e:
        print(f"Manual Queue Error: {e}")

def heart_beat():
    with open("/tmp/heartbeat", "w") as f: f.write(str(time.time()))
    broker = Broker()
    ok, msg = broker.test_connection()
    update_status("api_health", msg)
    if not ok: return

    # 1. Sync Statuses (Fixes the "Execution" tab not updating)
    sync_order_statuses(broker)

    # 2. Process Manual Queue
    process_manual_queue(broker)

    if get_status("engine_running") == "0": return
    if "Closed" in broker.get_market_clock(): return

    strategies = get_strategies()
    if not strategies: return

    stats = broker.get_account_stats()
    cash = stats.get('Cash', 0.0)
    equity = stats.get('Equity', 0.0)
    if len(strategies) > 0: target_per_stock = equity / len(strategies)
    else: target_per_stock = 0

    for sym, p in strategies.items():
        df = yf.download(sym, period="10d", interval="1h", progress=False)
        if df.empty or len(df) < 14: continue
        
        try:
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            logic = {'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}
            df_2h = df.resample('2h', origin='start_day').apply(logic).dropna()
            if len(df_2h) < 14: continue 

            close_series = df_2h['Close']
            high_series = df_2h['High']
            low_series = df_2h['Low']
            
            confirmed_rsi = RSIIndicator(close_series).rsi().iloc[-2]
            confirmed_adx = ADXIndicator(high_series, low_series, close_series).adx().iloc[-2]
        except: continue

        pos = broker.is_holding(sym)

        if not pos:
            if confirmed_adx > p.get('adx_trend', 25) and confirmed_rsi > p.get('rsi_trend', 50):
                price = broker.get_latest_price(sym) # Note: Broker needs get_latest_price method or use current_price from position check
                # Fallback if get_latest_price missing in broker snippet provided:
                # price = close_series.iloc[-1] 
                # Ideally, add get_latest_price to broker.py
                
                # Assuming broker has functionality or we use last close
                if price and cash > price:
                    qty = int(min(cash, target_per_stock) / price)
                    if qty >= 1:
                        tp_price = round(price * (1 + p['target']), 2)
                        sl_price = round(price * (1 - p['stop']), 2)
                        
                        success, order_id = broker.submit_order_v2(
                            "market", symbol=sym, qty=qty, side="buy", 
                            take_profit={"limit_price": tp_price}, 
                            stop_loss={"stop_price": sl_price}
                        )
                        if success:
                            send_trade_notification()
                            cash -= (qty * price) 
        else:
            if confirmed_rsi < 40:
                broker.close_position(sym)
                send_trade_notification()

if __name__ == "__main__":
    init_db()
    print("🚀 Algo-Trader Starting...")
    schedule.every(1).minutes.do(heart_beat)
    schedule.every().friday.at("23:00").do(schedule_async_tuner)
    while True:
        schedule.run_pending()
        time.sleep(1)