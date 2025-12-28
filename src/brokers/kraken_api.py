from src.utils.logger import setup_logger

logger = setup_logger("KrakenBroker")

class KrakenClient:
    def __init__(self):
        logger.warning("Kraken Client not yet implemented.")
        
    def get_price(self, symbol):
        pass