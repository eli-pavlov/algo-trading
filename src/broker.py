from alpaca.trading.client import TradingClient
from alpaca.trading.requests import (
    MarketOrderRequest, LimitOrderRequest, StopOrderRequest, 
    TakeProfitRequest, StopLossRequest, GetOrdersRequest
)
from alpaca.trading.enums import OrderSide, TimeInForce, OrderClass, OrderStatus
from alpaca.common.exceptions import APIError
from src.config import Config
from src.database import log_trade_attempt, update_trade_fill, DB_PATH
import sqlite3
from datetime import datetime, timezone

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
                close = clock.next_close.replace(tzinfo=timezone.utc)
                diff = close - now
                hours, rem = divmod(diff.seconds, 3600)
                mins, _ = divmod(rem, 60)
                return f"🟢 Market Open (Closes in {hours}h {mins}m)"
            else:
                return "🔴 Market Closed"
        except: return "🟠 Status Unavailable"

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
        try:
            return self.client.get_all_positions()
        except: return []

    def is_holding(self, symbol):
        try:
            # Returns Position object or raises error if not found
            return self.client.get_open_position(symbol)
        except: return None

    def close_position(self, symbol):
        try:
            self.client.close_position(symbol)
        except: pass

    # --- ADVANCED ORDERS (The New Stuff) ---

    def submit_order(self, symbol, qty, side, order_type, limit_px=None, stop_px=None, trail_pct=None):
        """
        Generic submitter for Manual Trading
        """
        # Convert string side to Enum
        side_enum = OrderSide.BUY if side.lower() == 'buy' else OrderSide.SELL
        
        req = None
        
        if order_type == "market":
            req = MarketOrderRequest(
                symbol=symbol,
                qty=qty,
                side=side_enum,
                time_in_force=TimeInForce.GTC
            )
        elif order_type == "limit":
            req = LimitOrderRequest(
                symbol=symbol,
                qty=qty,
                side=side_enum,
                time_in_force=TimeInForce.GTC,
                limit_price=limit_px
            )
        # Add other types as needed (stop, trailing, etc.)

        try:
            if req:
                order = self.client.submit_order(req)
                # Log to DB
                self._log_db(order.id, symbol, side, qty, order_type)
                return True, "Order Submitted"
            return False, "Invalid Order Config"
        except Exception as e:
            return False, str(e)

    def buy_bracket(self, symbol, qty, take_profit_price, stop_loss_price):
        """
        Sends a Buy Order + TP + SL in ONE API CALL.
        """
        req = MarketOrderRequest(
            symbol=symbol,
            qty=qty,
            side=OrderSide.BUY,
            time_in_force=TimeInForce.GTC,
            order_class=OrderClass.BRACKET,
            take_profit=TakeProfitRequest(limit_price=take_profit_price),
            stop_loss=StopLossRequest(stop_price=stop_loss_price)
        )
        
        try:
            order = self.client.submit_order(req)
            self._log_db(order.id, symbol, "buy", qty, "bracket")
            print(f"✅ Bracket Order Sent for {symbol}")
            return True
        except Exception as e:
            print(f"❌ Bracket Error: {e}")
            return False

    def get_latest_price(self, symbol):
        # NOTE: TradingClient doesn't have market data. 
        # For simplicity in this step, we can use yfinance or the historical client.
        # Ideally, we add StockHistoricalDataClient later.
        # For now, let's keep it simple using the snapshot approach or yfinance fallback.
        import yfinance as yf
        try:
            return yf.Ticker(symbol).fast_info['last_price']
        except: return 0.0

    def _log_db(self, oid, sym, side, qty, type):
        # Helper to log to SQLite
        try:
            log_trade_attempt(str(oid), sym, side, qty, type, 0.0, 0.0)
        except: pass

    def sync_tca_logs(self):
        """Syncs fill status from Alpaca to local DB"""
        with sqlite3.connect(DB_PATH) as conn:
            pending = conn.execute("SELECT order_id FROM trade_execution WHERE status='NEW'").fetchall()
        
        for (oid,) in pending:
            try:
                o = self.client.get_order_by_id(oid)
                if o.status == OrderStatus.FILLED and o.filled_avg_price:
                    update_trade_fill(oid, float(o.filled_avg_price), str(o.filled_at))
                elif o.status in [OrderStatus.CANCELED, OrderStatus.EXPIRED, OrderStatus.REJECTED]:
                     with sqlite3.connect(DB_PATH) as conn:
                        conn.execute("UPDATE trade_execution SET status=? WHERE order_id=?", (o.status, oid))
            except: pass