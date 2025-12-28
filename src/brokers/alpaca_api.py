import os
import alpaca_trade_api as tradeapi
from src.utils.logger import setup_logger

logger = setup_logger("AlpacaBroker")

class AlpacaClient:
    def __init__(self):
        self.api_key = os.getenv("ALPACA_API_KEY")
        self.secret_key = os.getenv("ALPACA_SECRET_KEY")
        self.base_url = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

        if not self.api_key or not self.secret_key:
            logger.critical("Alpaca API Keys missing! Check .env")
            raise ValueError("Missing Credentials")

        self.api = tradeapi.REST(
            key_id=self.api_key,
            secret_key=self.secret_key,
            base_url=self.base_url,
            api_version='v2'
        )
        logger.info(f"Connected to Alpaca at {self.base_url}")

    def get_account(self):
        try:
            return self.api.get_account()
        except Exception as e:
            logger.error(f"Error fetching account: {e}")
            return None

    def get_position(self, symbol):
        try:
            return self.api.get_position(symbol)
        except Exception:
            return None

    def has_open_order(self, symbol):
        """Checks if there are any open orders for this symbol to prevent stacking"""
        try:
            orders = self.api.list_orders(status='open', symbols=[symbol], limit=1)
            return len(orders) > 0
        except Exception as e:
            logger.error(f"Error checking open orders: {e}")
            return False

    def submit_bracket_order(self, symbol, qty, side, take_profit_price, stop_loss_price, client_order_id=None):
        try:
            # Prepare arguments, filtering out None for client_order_id if not provided
            params = {
                "symbol": symbol,
                "qty": qty,
                "side": side,
                "type": 'market',
                "time_in_force": 'gtc',
                "order_class": 'bracket',
                "take_profit": {'limit_price': take_profit_price},
                "stop_loss": {'stop_price': stop_loss_price}
            }
            
            if client_order_id:
                params["client_order_id"] = client_order_id

            order = self.api.submit_order(**params)
            logger.info(f"Order Submitted: {side} {qty} {symbol} (ID: {client_order_id})")
            return order
        except Exception as e:
            logger.error(f"Failed to submit order for {symbol}: {e}")
            return None