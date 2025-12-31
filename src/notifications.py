from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetOrdersRequest
from alpaca.trading.enums import QueryOrderStatus
from src.config import Config
import requests
import datetime

def _fmt_money_compact(val):
    """Shortens large numbers: 1200 -> 1.2K, 1500000 -> 1.5M"""
    abs_val = abs(val)
    if abs_val >= 1_000_000:
        return f"${val/1_000_000:.1f}M"
    elif abs_val >= 1_000:
        return f"${val/1_000:.1f}K"
    else:
        return f"${val:.2f}"

def send_trade_notification():
    """Compiles and sends the Slack report with compact formatting."""
    if not Config.REPORT_URL: return
    
    # Auth for the reporter
    key, secret, is_paper = Config.get_auth(Config.MODE)
    try:
        client = TradingClient(key, secret, paper=is_paper)
        acc = client.get_account()
        
        # Build Header
        msg = f"✅ **Trade Executed** ({Config.MODE})\n"
        msg += f"Time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        
        # Compact Financials
        eq_str = _fmt_money_compact(float(acc.portfolio_value))
        cash_str = _fmt_money_compact(float(acc.cash))
        msg += f"Equity: {eq_str} | Cash: {cash_str}\n"
        
        # Positions Data
        positions = client.get_all_positions()
        
        if positions:
            # Fetch Open Orders for Dist% Context
            req = GetOrdersRequest(status=QueryOrderStatus.OPEN, limit=500)
            orders = client.get_orders(req)
            
            # Map Orders
            orders_map = {}
            for o in orders:
                if o.symbol not in orders_map: orders_map[o.symbol] = []
                orders_map[o.symbol].append(o)

            msg += "\n**Positions:**\n"
            msg += "```\n"
            
            for p in positions:
                # 1. Basic Stats
                symbol = p.symbol
                mkt_val = float(p.market_value)
                pl_pct = float(p.unrealized_plpc) * 100
                
                # 2. Calculate Distance (Delta)
                dist_str = ""
                if symbol in orders_map:
                    current_price = float(p.current_price)
                    trigger_price = 0.0
                    
                    # Priority: Limit (TP) -> Stop (SL)
                    limit_orders = [o for o in orders_map[symbol] if o.limit_price]
                    if limit_orders:
                        trigger_price = float(limit_orders[0].limit_price)
                    else:
                        stop_orders = [o for o in orders_map[symbol] if o.stop_price]
                        if stop_orders:
                            trigger_price = float(stop_orders[0].stop_price)
                    
                    if trigger_price > 0 and current_price > 0:
                        dist = ((trigger_price - current_price) / current_price) * 100
                        dist_str = f" ∆{dist:+.0f}%"

                # 3. Format Line: "AMD   $2.3K   p/l:+1.5% ∆+5%"
                val_fmt = _fmt_money_compact(mkt_val)
                line = f"{symbol:<5} {val_fmt:<7} p/l:{pl_pct:+.1f}%{dist_str}\n"
                msg += line
                
            msg += "```"
            
        requests.post(Config.REPORT_URL, json={"text": msg})
    except Exception as e:
        print(f"Notification Error: {e}")