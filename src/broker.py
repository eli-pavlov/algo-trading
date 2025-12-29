import os
import requests
import alpaca_trade_api as tradeapi
import urllib3
from datetime import datetime, timezone

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class Broker:
    def __init__(self):
        self.base_url = "https://paper-api.alpaca.markets"
        self.api_key = os.getenv("APIKEY")
        self.secret_key = os.getenv("SECRETKEY")
        
        self.api = tradeapi.REST(
            key_id=self.api_key,
            secret_key=self.secret_key,
            base_url=self.base_url,
            api_version='v2'
        )
        self.api._session.trust_env = False
        self.api._session.verify = False

    def test_connection(self):
        try:
            acct = self.api.get_account()
            return True, f"🟢 Connected (ID: {acct.id})"
        except Exception as e:
            return False, f"🔴 Error: {str(e)}"

    def get_market_clock(self):
        """Returns market status and time to open/close."""
        try:
            clock = self.api.get_clock()
            now = clock.timestamp.replace(tzinfo=timezone.utc)
            
            if clock.is_open:
                close_time = clock.next_close.replace(tzinfo=timezone.utc)
                delta = close_time - now
                msg = f"🟢 Market Open (Closes in {str(delta).split('.')[0]})"
            else:
                open_time = clock.next_open.replace(tzinfo=timezone.utc)
                delta = open_time - now
                msg = f"🔴 Market Closed (Opens in {str(delta).split('.')[0]})"
            return msg
        except:
            return "🟠 Market Status Unavailable"

    def get_portfolio_history_stats(self):
        """Fetches 1D, 1W, 1M, 1A performance."""
        periods = {'1D': '1D', '1W': '1W', '1M': '1M', '1A': '1A'}
        data = {}
        for label, p in periods.items():
            try:
                # '1A' isn't standard in some versions, defaulting to '1M' if fails
                hist = self.api.get_portfolio_history(period=p, timeframe="1D")
                if hist.equity:
                    start = hist.equity[0]
                    end = hist.equity[-1]
                    pct = ((end - start) / start) * 100
                    data[label] = f"{pct:+.2f}%"
                else:
                    data[label] = "0.00%"
            except:
                data[label] = "N/A"
        return data

    def get_account_stats(self):
        try:
            acc = self.api.get_account()
            return {
                "Equity": float(acc.portfolio_value),
                "Power": float(acc.buying_power),
                "Cash": float(acc.cash)
            }
        except:
            return {}

    def get_orders_for_symbol(self, symbol):
        """Fetches active Stop Loss / Take Profit orders for a symbol."""
        try:
            orders = self.api.list_orders(status='open', symbols=[symbol])
            return [f"{o.type.upper()} {o.side} @ {o.limit_price or o.stop_price}" for o in orders]
        except:
            return []

    def submit_manual_order(self, symbol, qty, side, type, limit_px=None, stop_px=None, trail_pct=None):
        """Handles all API order types."""
        args = {
            "symbol": symbol,
            "qty": qty,
            "side": side,
            "type": type,
            "time_in_force": "gtc"
        }
        if type == 'limit': args['limit_price'] = limit_px
        if type == 'stop': args['stop_price'] = stop_px
        if type == 'stop_limit':
            args['stop_price'] = stop_px
            args['limit_price'] = limit_px
        if type == 'trailing_stop': args['trail_percent'] = trail_pct

        try:
            self.api.submit_order(**args)
            return True, "Order Submitted"
        except Exception as e:
            return False, str(e)

    # ... (Keep existing is_holding / sell_all / buy_bracket for the bot logic) ...
    def is_holding(self, symbol):
        try: return self.api.get_position(symbol)
        except: return None
    
    def sell_all(self, sym):
        try:
            pos = self.is_holding(sym)
            if pos:
                self.api.submit_order(symbol=sym, qty=pos.qty, side='sell', type='market', time_in_force='gtc')
        except: pass

    def buy_bracket(self, sym, qty, tp_pct, sl_pct):
        try:
            price = float(self.api.get_latest_trade(sym).price)
            self.api.submit_order(
                symbol=sym, qty=qty, side='buy', type='market', time_in_force='gtc',
                order_class='bracket',
                take_profit={'limit_price': round(price * (1 + tp_pct), 2)},
                stop_loss={'stop_price': round(price * (1 - sl_pct), 2)}
            )
        except: pass