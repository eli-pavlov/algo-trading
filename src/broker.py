import os
import sqlite3
import urllib3
from datetime import datetime, timezone
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import (
    MarketOrderRequest, LimitOrderRequest, TakeProfitRequest, 
    StopLossRequest, GetPortfolioHistoryRequest
)
from alpaca.trading.enums import OrderSide, TimeInForce, OrderClass, OrderStatus
from src.config import Config
from src.database import log_trade_attempt, update_trade_fill, DB_PATH

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class Broker:
    def __init__(self, mode=None):
        self.mode = mode or Config.MODE
        key, secret, is_paper = Config.get_auth(self.mode)
        
        # Initialize the new alpaca-py TradingClient
        self.client = TradingClient(api_key=key, secret_key=secret, paper=is_paper)

    def test_connection(self):
        try:
            acc = self.client.get_account()
            return True, f"Connected to {self.mode} ({acc.id})"
        except Exception as e:
            return False, str(e)

    def get_market_clock(self):
        """Checks if the market is open using the new alpaca-py Clock object."""
        try:
            clock = self.client.get_clock()
            now = datetime.now(timezone.utc)
            
            if clock.is_open:
                close_time = clock.next_close.replace(tzinfo=timezone.utc)
                diff = close_time - now
                hours, rem = divmod(int(diff.total_seconds()), 3600)
                mins, _ = divmod(rem, 60)
                return f"🟢 Market Open (Closes in {hours}h {mins}m)"
            else:
                open_time = clock.next_open.replace(tzinfo=timezone.utc)
                diff = open_time - now
                days = diff.days
                hours, rem = divmod(diff.seconds, 3600)
                mins, _ = divmod(rem, 60)
                if days > 0:
                    return f"🔴 Market Closed (Opens in {days}d {hours}h {mins}m)"
                return f"🔴 Market Closed (Opens in {hours}h {mins}m)"
        except Exception as e:
            print(f"Clock Error: {e}")
            return "🟠 Market Status Unavailable"

    def get_portfolio_history_stats(self):
        """Fetches history using the new GetPortfolioHistoryRequest model."""
        periods = {'1D': '1D', '1W': '1W', '1M': '1M', '1A': '1A'}
        data = {}
        for label, p in periods.items():
            try:
                req = GetPortfolioHistoryRequest(period=p, timeframe="1D")
                hist = self.client.get_portfolio_history(req)
                if hist and len(hist.equity) > 1:
                    start = float(hist.equity[0])
                    end = float(hist.equity[-1])
                    if start == 0: start = 1
                    pct = ((end - start) / start) * 100
                    data[label] = f"{pct:+.2f}%"
                else:
                    data[label] = "0.00%"
            except:
                data[label] = "N/A"
        return data

    def get_account_stats(self):
        try:
            acc = self.client.get_account()
            return {
                "Equity": float(acc.portfolio_value),
                "Power": float(acc.buying_power),
                "Cash": float(acc.cash)
            }
        except: return {}

    def get_all_positions(self):
        try: return self.client.get_all_positions()
        except: return []

    def is_holding(self, symbol):
        try: return self.client.get_open_position(symbol)
        except: return None

    # --- Execution Logic ---

    def submit_order(self, symbol, qty, side, order_type, limit_px=None):
        side_enum = OrderSide.BUY if side.lower() == 'buy' else OrderSide.SELL
        if order_type == "limit":
            req = LimitOrderRequest(symbol=symbol, qty=qty, side=side_enum, 
                                    time_in_force=TimeInForce.GTC, limit_price=limit_px)
        else:
            req = MarketOrderRequest(symbol=symbol, qty=qty, side=side_enum, 
                                     time_in_force=TimeInForce.GTC)
        try:
            order = self.client.submit_order(req)
            log_trade_attempt(str(order.id), symbol, side, qty, order_type, 0.0, 0.0)
            return True, "Order Submitted"
        except Exception as e:
            return False, str(e)

    def buy_bracket(self, symbol, qty, tp_price, sl_price):
        req = MarketOrderRequest(
            symbol=symbol, qty=qty, side=OrderSide.BUY, time_in_force=TimeInForce.GTC,
            order_class=OrderClass.BRACKET,
            take_profit=TakeProfitRequest(limit_price=tp_price),
            stop_loss=StopLossRequest(stop_price=sl_price)
        )
        try:
            order = self.client.submit_order(req)
            log_trade_attempt(str(order.id), symbol, "buy", qty, "bracket", 0.0, 0.0)
            return True
        except Exception as e:
            print(f"Bracket Error: {e}")
            return False

    def sync_tca_logs(self):
        with sqlite3.connect(DB_PATH) as conn:
            pending = conn.execute("SELECT order_id FROM trade_execution WHERE status='NEW'").fetchall()
        for (oid,) in pending:
            try:
                o = self.client.get_order_by_id(oid)
                if o.status == OrderStatus.FILLED and o.filled_avg_price:
                    update_trade_fill(oid, float(o.filled_avg_price), str(o.filled_at))
                elif o.status in [OrderStatus.CANCELED, OrderStatus.REJECTED]:
                    with sqlite3.connect(DB_PATH) as conn:
                        conn.execute("UPDATE trade_execution SET status=? WHERE order_id=?", (o.status, oid))
            except: pass