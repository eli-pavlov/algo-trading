import schedule, time
from src.database import init_db, get_strategies
from broker import Broker
import pandas_ta as ta
import yfinance as yf

broker = Broker()

def trade_loop():
    if not broker.api.get_clock().is_open: return
    
    strategies = get_strategies()
    for sym, p in strategies.items():
        pos = broker.is_holding(sym)
        
        # 1. Management (Trailing Stop)
        if pos:
            price = float(pos.current_price)
            new_stop = round(price * (1 - p['stop']), 2)
            # Only update if it moves up
            broker.update_stop(sym, pos.qty, new_stop)
            
        # 2. Entry Logic
        else:
            df = yf.download(sym, period="5d", interval="1h")
            adx = df.ta.adx().iloc[-1]['ADX_14']
            rsi = df.ta.rsi().iloc[-1]
            
            if adx > p['adx_trend'] and rsi > p['rsi_trend']:
                price = df['Close'].iloc[-1]
                broker.buy_bracket(sym, 1, price, price*(1+p['target']), price*(1-p['stop']))

if __name__ == "__main__":
    init_db()
    schedule.every(1).minutes.do(trade_loop)
    while True:
        schedule.run_pending()
        time.sleep(1)