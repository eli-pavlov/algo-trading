import alpaca_trade_api as tradeapi
import os

class Broker:
    def __init__(self):
        self.api = tradeapi.REST(
            os.getenv("API_KEY"), 
            os.getenv("SECRET_KEY"), 
            os.getenv("BASE_URL", "https://paper-api.alpaca.markets"), 
            'v2'
        )

    def is_holding(self, symbol):
        try: return self.api.get_position(symbol)
        except: return None

    def buy_bracket(self, sym, qty, tp_pct, sl_pct):
        price = float(self.api.get_latest_trade(sym).price)
        return self.api.submit_order(
            symbol=sym, qty=qty, side='buy', type='market', time_in_force='gtc', 
            order_class='bracket',
            take_profit={'limit_price': round(price * (1 + tp_pct), 2)},
            stop_loss={'stop_price': round(price * (1 - sl_pct), 2)}
        )