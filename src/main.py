import schedule
import time
import numpy as np
import yfinance as yf
import pandas as pd
from ta.trend import ADXIndicator
from ta.momentum import RSIIndicator
from src.database import init_db, get_strategies, get_status, update_status, get_pending_manual_orders, update_manual_order_status
from src.broker import Broker
from src.notifications import send_trade_notification

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
    # 1. Update Heartbeat File
    with open("/tmp/heartbeat", "w") as f: f.write(str(time.time()))

    broker = Broker()
    
    # 2. Check Connection
    ok, msg = broker.test_connection()
    update_status("api_health", msg)
    if not ok: return

    # 3. Manual Orders (Always run)
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
    target_per_stock = equity / len(strategies)

    for sym, p in strategies.items():
        # A. Get Data
        df = yf.download(sym, period="5d", interval="1h", progress=False)
        if df.empty: continue
        
        # B. Calc Indicators
        # (Assuming simple close series)
        close = df['Close']
        if isinstance(close, pd.DataFrame): close = close.iloc[:,0]
        
        try:
            rsi = RSIIndicator(close).rsi().iloc[-1]
            adx = ADXIndicator(df['High'], df['Low'], close).adx().iloc[-1]
        except: continue

        # C. Check Positions
        pos = broker.is_holding(sym)

        # D. Logic
        if not pos:
            # ENTRY
            if adx > p.get('adx_trend', 25) and rsi > p.get('rsi_trend', 50):
                price = broker.get_latest_price(sym)
                if price > 0 and cash > price:
                    qty = int(min(cash, target_per_stock) / price)
                    if qty >= 1:
                        # CALCULATE BRACKET PRICES
                        tp_price = round(price * (1 + p['target']), 2)
                        sl_price = round(price * (1 - p['stop']), 2)
                        
                        # EXECUTE BRACKET
                        if broker.buy_bracket(sym, qty, tp_price, sl_price):
                            send_trade_notification()
                            cash -= (qty * price) # Adjust local cash estimate
        else:
            # EXIT (Panic / Strategy Exit)
            # Note: The Bracket order handles TP/SL automatically!
            # We only need to force sell if RSI indicates a crash not caught by SL
            if rsi < 40:
                broker.close_position(sym)
                send_trade_notification()

if __name__ == "__main__":
    init_db()
    print("🚀 Algo-Trader (Alpaca-Py Edition) Starting...")
    schedule.every(1).minutes.do(heart_beat)
    while True:
        schedule.run_pending()
        time.sleep(1)