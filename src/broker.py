import os
import requests
import alpaca_trade_api as tradeapi
import urllib3

# Global SSL Bypass
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class Broker:
    def __init__(self):
        # CLEANUP: Strip /v2 or trailing slashes to avoid 404 errors
        raw_url = os.getenv("PAPER_URL", "https://paper-api.alpaca.markets")
        self.base_url = raw_url.replace('/v2', '').rstrip('/')
        
        self.api_key = os.getenv("APIKEY")
        self.secret_key = os.getenv("SECRETKEY")
        self.report_url = os.getenv("REPORT_LINK")

        # Initialize the REST client (it appends /v2 automatically)
        self.api = tradeapi.REST(
            key_id=self.api_key,
            secret_key=self.secret_key,
            base_url=self.base_url,
            api_version='v2'
        )
        
        # Force the session to ignore SSL verification
        self.api._session.verify = False

    def test_connection(self):
        """Perform a raw request to verify the URL and Keys manually."""
        try:
            url = f"{self.base_url}/v2/account"
            headers = {
                "APCA-API-KEY-ID": self.api_key,
                "APCA-API-SECRET-KEY": self.secret_key
            }
            response = requests.get(url, headers=headers, verify=False, timeout=5)
            if response.status_code == 200:
                return True, f"Connected to {self.base_url}"
            else:
                return False, f"HTTP {response.status_code}: {response.text}"
        except Exception as e:
            return False, f"Connection Failed: {str(e)}"

    def get_account_stats(self):
        try:
            account = self.api.get_account()
            return {
                "BUYING_POWER": f"${float(account.buying_power):,.2f}",
                "TOTAL_PORTFOLIO": f"${float(account.portfolio_value):,.2f}",
                "CASH": f"${float(account.cash):,.2f}"
            }
        except Exception as e:
            return {"ERROR": str(e)}

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
                    symbol=sym, qty=pos.qty, side='sell', 
                    type='market', time_in_force='gtc'
                )
                return True
        except:
            pass
        return False

    def buy_bracket(self, sym, qty, tp_pct, sl_pct):
        try:
            price = float(self.api.get_latest_trade(sym).price)
            return self.api.submit_order(
                symbol=sym, qty=qty, side='buy', type='market', 
                time_in_force='gtc', order_class='bracket',
                take_profit={'limit_price': round(price * (1 + tp_pct), 2)},
                stop_loss={'stop_price': round(price * (1 - sl_pct), 2)}
            )
        except:
            return None