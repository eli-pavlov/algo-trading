from alpaca.trading.client import TradingClient
from src.config import Config
import requests
import datetime

def send_trade_notification():
    """Compiles and sends the Slack report"""
    if not Config.REPORT_URL: return
    
    # Auth for the reporter
    key, secret, is_paper = Config.get_auth(Config.MODE)
    try:
        client = TradingClient(key, secret, paper=is_paper)
        acc = client.get_account()
        
        # Build Message
        msg = f"✅ **Trade Executed** ({Config.MODE})\n"
        msg += f"Time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        msg += f"Equity: ${float(acc.portfolio_value):.2f}\n"
        msg += f"Cash: ${float(acc.cash):.2f}\n"
        
        # Positions
        positions = client.get_all_positions()
        if positions:
            msg += "\n**Positions:**\n"
            msg += "```\n"
            for p in positions:
                pl_pct = float(p.unrealized_plpc) * 100
                msg += f"{p.symbol:<6} ${float(p.market_value):<8.2f} P/L: {pl_pct:+.2f}%\n"
            msg += "```"
            
        requests.post(Config.REPORT_URL, json={"text": msg})
    except Exception as e:
        print(f"Notification Error: {e}")