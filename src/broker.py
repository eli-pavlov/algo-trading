import os
import requests
import alpaca_trade_api as tradeapi


class Broker:
    def __init__(self):
        self.api = tradeapi.REST(
            os.getenv("APIKEY"),
            os.getenv("SECRETKEY"),
            os.getenv("PAPER_URL"),
            'v2'
        )
        self.webhook = os.getenv("REPORT_LINK")

    def report(self, message):
        if self.webhook:
            requests.post(self.webhook, json={"text": f"🤖 *Bot Alert:* {message}"})

    def is_holding(self, symbol):
        try:
            return self.api.get_position(symbol)
        except Exception:
            return None

    def buy_bracket(self, sym, qty, tp_pct, sl_pct):
        price = float(self.api.get_latest_trade(sym).price)
        order = self.api.submit_order(
            symbol=sym, qty=qty, side='buy', type='market', time_in_force='gtc',
            order_class='bracket',
            take_profit={'limit_price': round(price * (1 + tp_pct), 2)},
            stop_loss={'stop_price': round(price * (1 - sl_pct), 2)}
        )
        self.report(f"Entered {sym} at {price}. Target: +{tp_pct*100}%, SL: -{sl_pct*100}%")
        return order