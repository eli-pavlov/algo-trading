import os
import sqlite3
import urllib3
import pandas as pd
from datetime import datetime, timezone, timedelta
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import (
    MarketOrderRequest, LimitOrderRequest, TakeProfitRequest, 
    StopLossRequest, GetPortfolioHistoryRequest, GetOrdersRequest
)
from alpaca.trading.enums import OrderSide, TimeInForce, OrderClass, OrderStatus
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
                # Historical metrics restored for alpaca-py
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
        """Calculates mean API latency from SQLite for the last 24 hours."""
        try:
            with sqlite3.connect(DB_PATH) as conn:
                # SQLite timestamp filtering for last 24h
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
        """Fetches open orders (Limit, Stop, etc) for a specific ticker."""
        try:
            req = GetOrdersRequest(status=OrderStatus.OPEN, symbols=[symbol])
            return self.client.get_orders(req)
        except: return []

    def submit_order_v2(self, order_type, **kwargs):
        """Expanded submitter to handle advanced order types from UI."""
        try:
            # Map string to Enum
            kwargs['side'] = OrderSide.BUY if kwargs['side'].lower() == 'buy' else OrderSide.SELL
            kwargs['time_in_force'] = TimeInForce.GTC if kwargs['time_in_force'].lower() == 'gtc' else TimeInForce.DAY
            
            # Use appropriate Request model
            if order_type == "market": req = MarketOrderRequest(**kwargs)
            elif order_type == "limit": req = LimitOrderRequest(**kwargs)
            # ... handle others ...
            
            order = self.client.submit_order(req)
            log_trade_attempt(str(order.id), kwargs['symbol'], str(kwargs['side']), kwargs['qty'], order_type, 0.0, 0.0)
            return True, order.id
        except Exception as e: return False, str(e)