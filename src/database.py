import os
import time
import requests
import alpaca_trade_api as tradeapi
import urllib3
from datetime import datetime, timezone
from src.database import log_trade_attempt, update_trade_fill, DB_PATH
import sqlite3

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
            return True, f"Connected to {acct.id}"
        except Exception as e:
            return False, str(e)

    def get_market_clock(self):
        try:
            clock = self.api.get_clock()
            now = clock.timestamp.replace(tzinfo=timezone.utc)
            if clock.is_open:
                close_time = clock.next_close.replace(tzinfo=timezone.utc)
                diff = close_time - now
                hours, remainder = divmod(diff.seconds, 3600)
                mins, _ = divmod(remainder, 60)
                return f"🟢 Market Open (Closes in {hours}h {mins}m)"
            else:
                open_time = clock.next_open.replace(tzinfo=timezone.utc)
                diff = open_time - now
                days = diff.days
                hours, remainder = divmod(diff.seconds, 3600)
                mins, _ = divmod(remainder, 60)
                if days > 0: return f"🔴 Market Closed (Opens in {days} days, {hours}h {mins}m)"
                else: return f"🔴 Market Closed (Opens in {hours}h {mins}m)"
        except: return "🟠 Market Status Unavailable"

    def get_portfolio_history_stats(self):
        periods = {'1D': '1D', '1W': '1W', '1M': '1M', '1A': '1A'}
        data = {}
        for label, p in periods.items():
            try:
                hist = self.api.get_portfolio_history(period=p, timeframe="1D")
                if hist.equity:
                    start = hist.equity[0]; end = hist.equity[-1]
                    if start == 0: start = 1
                    pct = ((end - start) / start) * 100
                    data[label] = f"{pct:+.2f}%"
                else: data[label] = "0.00%"
            except: data[label] = "N/A"
        return data

    def get_account_stats(self):
        try:
            acc = self.api.get_account()
            return {"Equity": float(acc.portfolio_value), "Power": float(acc.buying_power), "Cash": float(acc.cash)}
        except: return {}

    def get_orders_for_symbol(self, symbol):
        try:
            orders = self.api.list_orders(status='open', symbols=[symbol])
            return [f"{o.type.upper()} {o.side} @ {o.limit_price or o.stop_price}" for o in orders]
        except: return []

    def has_open_order(self, symbol):
        try:
            orders = self.api.list_orders(status='open', symbols=[symbol])
            return len(orders) > 0
        except: return True # Fail-safe

    def is_holding(self, symbol):
        try: return self.api.get_position(symbol)
        except: return None

    def sell_all(self, sym):
        try:
            pos = self.is_holding(sym)
            if pos:
                self.api.submit_order(symbol=sym, qty=pos.qty, side='sell', type='market', time_in_force='gtc')
        except: pass

    # --- UPDATED METHODS FOR TCA ---

    def _get_snapshot_price(self, symbol):
        try:
            return float(self.api.get_latest_trade(symbol).price)
        except: return 0.0

    def submit_manual_order(self, symbol, qty, side, type, limit_px=None, stop_px=None, trail_pct=None):
        args = {"symbol": symbol, "qty": qty, "side": side, "type": type, "time_in_force": "gtc"}
        if limit_px: args['limit_price'] = limit_px
        if stop_px: args['stop_price'] = stop_px
        if trail_pct: args['trail_percent'] = trail_pct

        try:
            snap_px = self._get_snapshot_price(symbol)
            start_t = time.time()
            order = self.api.submit_order(**args)
            lat_ms = (time.time() - start_t) * 1000
            
            log_trade_attempt(order.id, symbol, side, qty, type, snap_px, lat_ms)
            return True, f"Submitted in {lat_ms:.0f}ms"
        except Exception as e:
            return False, str(e)

    def buy_bracket(self, sym, qty, tp_pct, sl_pct):
        try:
            snap_px = self._get_snapshot_price(sym)
            if snap_px == 0: return
            
            start_t = time.time()
            order = self.api.submit_order(
                symbol=sym, qty=qty, side='buy', type='market', time_in_force='gtc',
                order_class='bracket',
                take_profit={'limit_price': round(snap_px * (1 + tp_pct), 2)},
                stop_loss={'stop_price': round(snap_px * (1 - sl_pct), 2)}
            )
            lat_ms = (time.time() - start_t) * 1000
            
            log_trade_attempt(order.id, sym, 'buy', qty, 'market_bracket', snap_px, lat_ms)
        except Exception as e:
            print(f"Bracket Error: {e}")

    def sync_tca_logs(self):
        try:
            with sqlite3.connect(DB_PATH) as conn:
                pending = conn.execute("SELECT order_id FROM trade_execution WHERE status='NEW'").fetchall()
            
            for (oid,) in pending:
                try:
                    o = self.api.get_order(oid)
                    if o.status == 'filled' and o.filled_avg_price:
                        update_trade_fill(oid, float(o.filled_avg_price), str(o.filled_at))
                    elif o.status in ['canceled', 'expired', 'rejected']:
                         with sqlite3.connect(DB_PATH) as conn:
                             conn.execute("UPDATE trade_execution SET status=? WHERE order_id=?", (o.status.upper(), oid))
                except: pass
        except: pass