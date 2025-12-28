import os
import alpaca_trade_api as tradeapi
from src.utils.logger import setup_logger

logger = setup_logger("AlpacaBroker")

class AlpacaClient:
    def __init__(self):
        # API Keys are loaded from Environment Variables (Docker/Jenkins injects them)
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
            # Returns None if no position exists
            return None

    def submit_bracket_order(self, symbol, qty, side, take_profit_price, stop_loss_price):
        """
        Submits a market order with attached Take Profit and Stop Loss
        """
        try:
            order = self.api.submit_order(
                symbol=symbol,
                qty=qty,
                side=side,
                type='market',
                time_in_force='gtc',
                order_class='bracket',
                take_profit={'limit_price': take_profit_price},
                stop_loss={'stop_price': stop_loss_price}
            )
            logger.info(f"Order Submitted: {side} {qty} {symbol}")
            return order
        except Exception as e:
            logger.error(f"Failed to submit order for {symbol}: {e}")
            return None