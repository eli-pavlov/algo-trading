import os
import requests
import alpaca_trade_api as tradeapi
import urllib3

# Disable the "InsecureRequestWarning" to keep logs clean
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class Broker:
    def __init__(self):
        self.api_key = os.getenv("APIKEY")
        self.secret_key = os.getenv("SECRETKEY")
        self.base_url = os.getenv("PAPER_URL")
        self.report_url = os.getenv("REPORT_LINK")

        # Initialize the REST client
        self.api = tradeapi.REST(
            key_id=self.api_key,
            secret_key=self.secret_key,
            base_url=self.base_url,
            api_version='v2'
        )

        # GLOBAL FIX: Force the underlying requests session to ignore SSL verification
        self.api._session.verify = False

    def send_webhook_report(self, data_dict, title=None):
        if not self.report_url:
            return False
        header = f"🤖 *{title}*\n" if title else ""
        body = "\n".join([f"{key}: {value}" for key, value in data_dict.items()])
        try:
            requests.post(self.report_url, json={"text": f"{header}{body}"}, verify=False)
            return True
        except:
            return False

    def get_performance_summary(self):
        stats = {"Day": "1D", "Month": "1M", "Year": "1A", "Total": "all"}
        results = {}
        for label, period in stats.items():
            try:
                history = self.api.get_portfolio_history(period=period, timeframe="1D")
                equity = list(getattr(history, "equity", []) or [])
                base = float(getattr(history, "base_value", 0))
                if equity and base > 0:
                    pct = (float(equity[-1]) / base - 1.0) * 100.0
                    results[label] = f"{pct:+.2f}%"
                else:
                    results[label] = "0.00%"
            except:
                results[label] = "N/A"
        return results

    def get_account_stats(self):
        try:
            account = self.api.get_account()
            return {
                "BUYING_POWER": f"${float(account.buying_power):,.2f}",
                "TOTAL_PORTFOLIO": f"${float(account.portfolio_value):,.2f}",
                "CASH": f"${float(account.cash):,.2f}"
            }
        except Exception as e:
            return {"ERROR": "API Connection Failed", "DETAILS": str(e)}

    def is_holding(self, symbol):
        try:
            return self.api.get_position(symbol)
        except:
            return None

    def sell_all(self, sym):
        """Liquidates the entire position for a specific symbol."""
        try:
            pos = self.is_holding(sym)
            if pos:
                self.api.submit_order(
                    symbol=sym,
                    qty=pos.qty,
                    side='sell',
                    type='market',
                    time_in_force='gtc'
                )
                self.send_webhook_report({
                    "Action": "EXIT SIGNAL",
                    "Symbol": sym,
                    "Qty": pos.qty
                }, title="📉 POSITION CLOSED")
                return True
        except Exception as e:
            print(f"Error selling {sym}: {e}")
        return False

    def buy_bracket(self, sym, qty, tp_pct, sl_pct):
        try:
            price = float(self.api.get_latest_trade(sym).price)
            order = self.api.submit_order(
                symbol=sym,
                qty=qty,
                side='buy',
                type='market',
                time_in_force='gtc',
                order_class='bracket',
                take_profit={'limit_price': round(price * (1 + tp_pct), 2)},
                stop_loss={'stop_price': round(price * (1 - sl_pct), 2)}
            )
            self.send_webhook_report({
                "Action": "ENTRY EXECUTED",
                "Symbol": sym,
                "Price": f"${price}",
                "Qty": qty
            }, title="🚀 NEW TRADE")
            return order
        except Exception as e:
            self.send_webhook_report({"Error": str(e)}, title="🚨 TRADE FAILED")
            return None