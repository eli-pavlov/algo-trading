import os

class Config:
    # Mode: PAPER or LIVE
    MODE = os.getenv("TRADING_MODE", "PAPER").upper()
    
    # Paper Credentials
    API_KEY_PAPER = os.getenv("APIKEY_PAPER")
    API_SECRET_PAPER = os.getenv("SECRETKEY_PAPER")
    
    # Live Credentials
    API_KEY_LIVE = os.getenv("APIKEY_LIVE")
    API_SECRET_LIVE = os.getenv("SECRETKEY_LIVE")
    
    # URLs (Optional override, alpaca-py handles this mostly)
    PAPER_URL = "https://paper-api.alpaca.markets"
    LIVE_URL = "https://api.alpaca.markets"
    
    # Slack
    REPORT_URL = os.getenv("REPORT_LINK")
    
    # DB
    DB_PATH = os.getenv("DB_PATH", "data/trading.db")

    @classmethod
    def get_auth(cls, mode=None):
        """Returns (api_key, secret_key, is_paper)"""
        target = mode or cls.MODE
        if target == "LIVE":
            return cls.API_KEY_LIVE, cls.API_SECRET_LIVE, False
        return cls.API_KEY_PAPER, cls.API_SECRET_PAPER, True