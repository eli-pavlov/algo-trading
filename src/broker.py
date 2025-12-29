import alpaca_trade_api as tradeapi
import os

class Broker:
    def __init__(self):
        self.api = tradeapi.REST(os.getenv("API_KEY"), os.getenv("SECRET_KEY"), os.getenv("BASE_URL"), 'v2')

    def is_holding(self, symbol):
        try: return self.api.get_position(symbol)
        except: return None

    def buy_bracket(self, sym, qty, price, tp, sl):
        return self.api.submit_order(symbol=sym, qty=qty, side='buy', type='market', 
                                     time_in_force='gtc', order_class='bracket',
                                     take_profit={'limit_price': tp}, stop_loss={'stop_price': sl})

    def update_stop(self, sym, qty, new_stop):
        orders = self.api.list_orders(status='open', symbols=[sym])
        for o in orders: 
            if o.type == 'stop': self.api.cancel_order(o.id)
        return self.api.submit_order(symbol=sym, qty=qty, side='sell', type='stop', 
                                     time_in_force='gtc', stop_price=new_stop)