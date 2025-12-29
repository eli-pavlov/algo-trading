import os
import requests
import alpaca_trade_api as tradeapi
import urllib3
from requests.adapters import HTTPAdapter

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class Broker:
    def __init__(self):
        self.api_key = os.getenv("APIKEY")
        self.secret_key = os.getenv("SECRETKEY")
        self.base_url = os.getenv("PAPER_URL")
        self.report_url = os.getenv("REPORT_LINK")

        # Create a custom session that ignores SSL
        self.session = requests.Session()
        self.session.verify = False
        adapter = HTTPAdapter(max_retries=3)
        self.session.mount('https://', adapter)

        # Initialize the REST client with the custom session
        self.api = tradeapi.REST(
            key_id=self.api_key,
            secret_key=self.secret_key,
            base_url=self.base_url,
            api_version='v2'
        )
        # Inject the insecure session into the alpaca client
        self.api._session = self.session

    def test_connection(self):
        """Returns (Success: bool, Message: str)"""
        try:
            if not self.api_key or not self.secret_key:
                return False, "Missing API Keys in .env"
            acc = self.api.get_account()
            return True, f"Connected as {acc.id}"
        except Exception as e:
            return False, str(e)

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

    def list_positions(self):
        try:
            return self.api.list_positions()
        except Exception as e:
            return {"ERROR": str(e)}

    def send_webhook_report(self, data_dict, title=None):
        if not self.report_url: return False
        header = f"🤖 *{title}*\n" if title else ""
        body = "\n".join([f"{key}: {value}" for key, value in data_dict.items()])
        try:
            requests.post(self.report_url, json={"text": f"{header}{body}"}, verify=False, timeout=5)
            return True
        except: return False

    def is_holding(self, symbol):
        try: return self.api.get_position(symbol)
        except: return None