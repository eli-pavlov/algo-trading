import os
import requests
import alpaca_trade_api as tradeapi


class Broker:
    def __init__(self):
        """
        Initializes the Alpaca REST client and Slack reporting link using
        environment variables defined in your .env file.
        """
        self.api_key = os.getenv("APIKEY")
        self.secret_key = os.getenv("SECRETKEY")
        self.base_url = os.getenv("PAPER_URL")
        self.report_url = os.getenv("REPORT_LINK")

        self.api = tradeapi.REST(
            key_id=self.api_key,
            secret_key=self.secret_key,
            base_url=self.base_url,
            api_version='v2'
        )

    # --- REPORTING LOGIC (From your working script) ---

    def send_webhook_report(self, data_dict, title=None):
        """
        Sends a multi-line payload to Slack.
        """
        if not self.report_url:
            return

        header = f"🤖 *{title}*\n" if title else ""
        body = "\n".join([f"{key}: {value}" for key, value in data_dict.items()])
        
        payload = {"text": f"{header}{body}"}
        
        try:
            response = requests.post(self.report_url, json=payload)
            return response.status_code == 200
        except Exception as e:
            print(f"Failed to send webhook: {e}")
            return False

    def get_performance_summary(self):
        """
        Calculates performance for Day, Month, Year, and Total.
        """
        periods = {
            "Day": {"p": "1D", "t": "15Min"},
            "Month": {"p": "1M", "t": "1D"},
            "Year": {"p": "1A", "t": "1D"},
            "Total": {"p": "all", "t": "1D"}
        }
        
        results = {}
        for label, cfg in periods.items():
            try:
                history = self.api.get_portfolio_history(
                    period=cfg["p"], 
                    timeframe=cfg["t"]
                )
                equity = list(getattr(history, "equity", []) or [])
                base_value = float(getattr(history, "base_value", 0))
                
                if not equity or base_value <= 0:
                    results[label] = "N/A"
                    continue
                
                pct = (float(equity[-1]) / base_value - 1.0) * 100.0
                results[label] = f"{pct:+.2f}%"
            except Exception:
                results[label] = "Error"
        
        return results

    # --- TRADING LOGIC ---

    def is_holding(self, symbol):
        """
        Checks if a position currently exists for the symbol.
        """
        try:
            return self.api.get_position(symbol)
        except Exception:
            return None

    def get_account_stats(self):
        """
        Returns basic account metrics.
        """
        account = self.api.get_account()
        return {
            "BUYING_POWER": f"${float(account.buying_power):,.2f}",
            "TOTAL_PORTFOLIO": f"${float(account.portfolio_value):,.2f}",
            "CASH": f"${float(account.cash):,.2f}"
        }

    def buy_bracket(self, sym, qty, tp_pct, sl_pct):
        """
        Submits a market order with attached Take Profit and Stop Loss.
        """
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
            
            # Immediate Slack Notification
            self.send_webhook_report({
                "Action": "BUY BRACKET",
                "Symbol": sym,
                "Price": f"${price}",
                "Target": f"+{tp_pct*100}%",
                "Stop": f"-{sl_pct*100}%"
            }, title="TRADE EXECUTED")
            
            return order
        except Exception as e:
            self.send_webhook_report({"Error": str(e)}, title="TRADE FAILED")
            return None