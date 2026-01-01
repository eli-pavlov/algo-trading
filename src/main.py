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
    print("🧠 Starting Scheduled Weekly Tuning (Background Thread)...")
    try:
        # 🟢 LAZY IMPORT: Prevents Circular Import Crash at Startup
        from src.tuner import optimize_stock, TICKERS
        
        broker_tuner = Broker()
        for t in TICKERS:
            optimize_stock(t, broker_tuner)
        print("✅ Weekly Tuning Complete. New strategies saved to DB.")
    except Exception as e:
        print(f"❌ Tuning Thread Error: {e}")

def schedule_async_tuner():
    """Spawns the tuner thread so the main loop doesn't freeze."""
    print("⏳ Triggering Async Tuner...")
    t = threading.Thread(target=_run_tuner_job)
    t.start()

# --- SYNC LOGIC ---
def sync_order_statuses(broker):
    """Checks Alpaca for updates on orders we think are still 'NEW'."""
    try:
        pending = get_unfilled_executions()
        if not pending: return

        for (oid,) in pending:
            try:
                alpaca_order = broker.client.get_order_by_id(oid)
                if alpaca_order.status == 'filled':
                    update_trade_fill(oid, float(alpaca_order.filled_avg_price), alpaca_order.filled_at, 'FILLED')
                    print(f"🔄 Synced Fill: {oid}")
                elif alpaca_order.status in ['canceled', 'expired', 'rejected']:
                    update_trade_fill(oid, 0.0, str(datetime.utcnow()), alpaca_order.status.upper())
                    print(f"🔄 Synced Cancel: {oid}")
            except: pass
    except Exception as e: print(f"Sync Error: {e}")

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

    sync_order_statuses(broker)
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

            confirmed_rsi = RSIIndicator(df_2h['Close']).rsi().iloc[-2]
            confirmed_adx = ADXIndicator(df_2h['High'], df_2h['Low'], df_2h['Close']).adx().iloc[-2]
        except: continue

        pos = broker.is_holding(sym)
        if not pos:
            if confirmed_adx > p.get('adx_trend', 25) and confirmed_rsi > p.get('rsi_trend', 50):
                price = broker.get_latest_price(sym)
                if price and cash > price:
                    qty = int(min(cash, target_per_stock) / price)
                    if qty >= 1:
                        tp = round(price * (1 + p['target']), 2)
                        sl = round(price * (1 - p['stop']), 2)
                        success, _ = broker.submit_order_v2("market", symbol=sym, qty=qty, side="buy", 
                                                          take_profit={"limit_price": tp}, 
                                                          stop_loss={"stop_price": sl})
                        if success:
                            send_trade_notification()
                            cash -= (qty * price) 
        else:
            if confirmed_rsi < 40:
                broker.close_position(sym)
                send_trade_notification()

if __name__ == "__main__":
    init_db()
    print("🚀 Algo-Trader (2H Strategy + Async Tuner) Starting...")
    schedule.every(1).minutes.do(heart_beat)
    schedule.every().friday.at("23:00").do(schedule_async_tuner)
    while True:
        schedule.run_pending()
        time.sleep(1)