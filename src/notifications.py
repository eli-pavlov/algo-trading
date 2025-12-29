import os
import time
import requests
from datetime import datetime
from alpaca_trade_api.rest import REST

# --- Configuration (Reads from Docker ENV) ---
API_KEY_LIVE = os.getenv("APIKEY_LIVE") or os.getenv("APIKEY") # Fallback to default if specific not found
API_SECRET_LIVE = os.getenv("SECRETKEY_LIVE") or os.getenv("SECRETKEY")
URL_LIVE = os.getenv("LIVE_URL", "https://api.alpaca.markets")

API_KEY_PAPER = os.getenv("APIKEY_PAPER")
API_SECRET_PAPER = os.getenv("SECRETKEY_PAPER")
URL_PAPER = os.getenv("PAPER_URL", "https://paper-api.alpaca.markets")

REPORT_URL = os.getenv("REPORT_LINK")

def get_portfolio_value_usd(api):
    try:
        account = api.get_account()
        return float(account.portfolio_value)
    except: return 0.0

def get_buying_power(api):
    try:
        account = api.get_account()
        return float(account.buying_power)
    except: return 0.0

def get_all_balances_sorted(api):
    try:
        positions = api.list_positions()
        account = api.get_account()
        orders = api.list_orders()
    except: return {}
    
    # 1. Start with Cash
    ordered_balances = {}
    ordered_balances[f"{'USD':<6}"] = f"${float(account.cash):.2f}"

    # 2. Collect and Sort Positions
    position_list = []
    for position in positions:
        market_val = float(position.market_value) if position.market_value else 0.0
        position_list.append({
            'symbol': position.symbol,
            'market_value': market_val,
            'pl_pct': float(position.unrealized_plpc) * 100
        })
    
    # Sort: P/L Descending
    position_list.sort(key=lambda x: x['pl_pct'], reverse=True)

    # 3. Format Strings for Alignment
    for pos in position_list:
        key = f"{pos['symbol']:<6}"
        val_str = f"${pos['market_value']:.2f}"
        value = f"{val_str:<10} P/L: {pos['pl_pct']:+.2f}%"
        ordered_balances[key] = value

    # 4. Add Open Orders
    for order in orders:
        if order.status in ("open", "accepted"):
            stock_name = order.symbol
            key = f"{stock_name:<6}"
            if not any(k.strip() == stock_name for k in ordered_balances):
                ordered_balances[key] = f"{'$0.00':<10} (Open Order)"

    return ordered_balances

def send_webhook_report(data, as_code_block=False):
    if not REPORT_URL: return
    lines = [f"{key}: {value}" for key, value in data.items()]
    text_block = "\n".join(lines)
    if as_code_block: text_block = f"```\n{text_block}\n```"
    try:
        requests.post(REPORT_URL, json={"text": text_block})
    except Exception as e: print(f"Webhook Error: {e}")

def _fmt_pct(pct):
    return "N/A" if pct is None else f"{pct:+.2f}%"

def _first_nonzero(values):
    for v in values:
        try:
            fv = float(v)
            if fv > 0: return fv
        except: continue
    return None

def get_portfolio_return_pct(api, period, timeframe="1D", extended_hours=False):
    try:
        history = api.get_portfolio_history(period=period, timeframe=timeframe, extended_hours=extended_hours)
    except: return None

    equity_series = list(getattr(history, "equity", []) or [])
    if not equity_series: return None

    try: end_equity = float(equity_series[-1])
    except: return None

    base_value = float(getattr(history, "base_value", 0) or 0)
    if base_value <= 0: base_value = _first_nonzero(equity_series) or 0.0
    if base_value <= 0: return None

    return (end_equity / base_value - 1.0) * 100.0

def get_performance_summary(api):
    day_pct = get_portfolio_return_pct(api, "1D", "15Min", True)
    month_pct = get_portfolio_return_pct(api, "1M", "1D", False)
    year_pct = get_portfolio_return_pct(api, "1A", "1D", False)
    total_pct = get_portfolio_return_pct(api, "all", "1D", False)
    
    return {
        "Day": _fmt_pct(day_pct),
        "Month": _fmt_pct(month_pct),
        "Year": _fmt_pct(year_pct),
        "Total": _fmt_pct(total_pct),
    }

def run_report_cycle(api, label):
    balances = get_all_balances_sorted(api)
    if balances:
        # 1. Header
        send_webhook_report({
            "--------------------------------------": "",
            f"📊 {label}": "",
            "--------------------------------------": ""
        }, as_code_block=False)

        # 2. Stock List
        send_webhook_report(balances, as_code_block=True)
        
        # 3. Financials
        send_webhook_report({
            "BUYING_POWER": f"${get_buying_power(api):.2f}",
            "TOTAL_PORTFOLIO": f"${get_portfolio_value_usd(api):.2f}",
        }, as_code_block=False)

        # 4. Performance
        send_webhook_report({"Performance Metrics": ""}, as_code_block=False)
        send_webhook_report(get_performance_summary(api), as_code_block=False)

def send_trade_notification():
    """Main entry point called by the bot"""
    print("📤 Sending Slack Report...")
    
    # Send Time Header
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    send_webhook_report({"✅ Trade Executed": "", "Time": current_time}, as_code_block=False)

    # Report LIVE (If configured)
    if API_KEY_LIVE and API_SECRET_LIVE:
        try:
            live_api = REST(API_KEY_LIVE, API_SECRET_LIVE, URL_LIVE)
            run_report_cycle(live_api, "LIVE ACCOUNT")
        except Exception as e: print(f"Live Report Error: {e}")

    # Report PAPER (If configured)
    if API_KEY_PAPER and API_SECRET_PAPER:
        try:
            paper_api = REST(API_KEY_PAPER, API_SECRET_PAPER, URL_PAPER)
            run_report_cycle(paper_api, "PAPER ACCOUNT")
        except Exception as e: print(f"Paper Report Error: {e}")