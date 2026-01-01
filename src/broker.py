import os
import sqlite3
import urllib3
import time  # <--- Make sure this is imported
import pandas as pd
from datetime import datetime, timezone, timedelta
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import (
    MarketOrderRequest, LimitOrderRequest, TakeProfitRequest, 
    StopLossRequest, GetPortfolioHistoryRequest, GetOrdersRequest
)
from alpaca.trading.enums import OrderSide, TimeInForce, OrderClass, OrderStatus, QueryOrderStatus
from src.config import Config
from src.database import log_trade_attempt, update_trade_fill, DB_PATH

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class Broker:
    def __init__(self, mode=None):
        self.mode = mode or Config.MODE
        key, secret, is_paper = Config.get_auth(self.mode)
        self.client = TradingClient(api_key=key, secret_key=secret, paper=is_paper)

    def test_connection(self):
        try:
            acc = self.client.get_account()
            return True, f"Connected to {self.mode} ({acc.id})"
        except Exception as e:
            return False, str(e)

    # --- NEW: LIVE PING FUNCTION ---
    def ping(self):
        """Measures real-time round-trip latency to Alpaca API."""
        try:
            t0 = time.time()
            self.client.get_clock() # Lightweight call
            return (time.time() - t0) * 1000
        except:
            return -1.0

    def get_market_clock(self):
        try:
            clock = self.client.get_clock()
            now = datetime.now(timezone.utc)
            if clock.is_open:
                close_time = clock.next_close.replace(tzinfo=timezone.utc)
                diff = close_time - now
                h, r = divmod(int(diff.total_seconds()), 3600)
                m, _ = divmod(r, 60)
                return f"🟢 Market Open (Closes in {h}h {m}m)"
            else:
                open_time = clock.next_open.replace(tzinfo=timezone.utc)
                diff = open_time - now
                d, h = diff.days, diff.seconds // 3600
                m = (diff.seconds % 3600) // 60
                return f"🔴 Market Closed (Opens in {f'{d}d ' if d>0 else ''}{h}h {m}m)"
        except: return "🟠 Status Unavailable"

    def get_portfolio_history_stats(self):
        periods = {'1D': '1D', '1W': '1W', '1M': '1M', '1A': '1A'}
        data = {}
        for label, p in periods.items():
            try:
                req = GetPortfolioHistoryRequest(period=p, timeframe="1D")
                hist = self.client.get_portfolio_history(req)
                if hist and len(hist.equity) > 1:
                    start, end = float(hist.equity[0]), float(hist.equity[-1])
                    pct = ((end - (start or 1)) / (start or 1)) * 100
                    data[label] = f"{pct:+.2f}%"
                else: data[label] = "0.00%"
            except: data[label] = "N/A"
        return data

    def get_mean_latency_24h(self):
        """Still useful for historical analysis, but not for the live dashboard."""
        try:
            with sqlite3.connect(DB_PATH) as conn:
                query = """
                    SELECT AVG(api_latency_ms) FROM trade_execution 
                    WHERE submitted_at >= datetime('now', '-24 hours')
                """
                res = conn.execute(query).fetchone()
                return res[0] if res[0] else 0.0
        except: return 0.0

    def get_account_stats(self):
        try:
            acc = self.client.get_account()
            return {"Equity": float(acc.portfolio_value), "Power": float(acc.buying_power), "Cash": float(acc.cash)}
        except: return {}

    def get_all_positions(self):
        try: return self.client.get_all_positions()
        except: return []

    def is_holding(self, symbol):
        try: return self.client.get_open_position(symbol)
        except: return None

    def get_orders_for_symbol(self, symbol):
        try:
            req = GetOrdersRequest(status=QueryOrderStatus.ALL, symbols=[symbol], limit=50)
            all_orders = self.client.get_orders(req)
            active_orders = []
            terminal_states = [OrderStatus.FILLED, OrderStatus.CANCELED, OrderStatus.EXPIRED, OrderStatus.REJECTED]
            for o in all_orders:
                if o.status not in terminal_states:
                    active_orders.append(o)
            return active_orders
        except Exception as e: 
            print(f"Order fetch error: {e}")
            return []

    def submit_order_v2(self, order_type, **kwargs):
        try:
            kwargs['side'] = OrderSide.BUY if kwargs['side'].lower() == 'buy' else OrderSide.SELL
            kwargs['time_in_force'] = TimeInForce.GTC if kwargs['time_in_force'].lower() == 'gtc' else TimeInForce.DAY
            
            if order_type == "market": req = MarketOrderRequest(**kwargs)
            elif order_type == "limit": req = LimitOrderRequest(**kwargs)
            
            t0 = time.time()
            order = self.client.submit_order(req)
            latency_ms = (time.time() - t0) * 1000
            
            log_trade_attempt(str(order.id), kwargs['symbol'], str(kwargs['side']), kwargs['qty'], order_type, 0.0, latency_ms)
            return True, order.id
        except Exception as e: return False, str(e)