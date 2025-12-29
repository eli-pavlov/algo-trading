import os

class Config:
    MODE = os.getenv("TRADING_MODE", "PAPER").upper()
    
    # Paper Credentials with Fallback
    API_KEY_PAPER = os.getenv("APIKEY_PAPER") or os.getenv("APIKEY")
    API_SECRET_PAPER = os.getenv("SECRETKEY_PAPER") or os.getenv("SECRETKEY")
    
    # Live Credentials with Fallback
    API_KEY_LIVE = os.getenv("APIKEY_LIVE") or os.getenv("APIKEY")
    API_SECRET_LIVE = os.getenv("SECRETKEY_LIVE") or os.getenv("SECRETKEY")
    
    PAPER_URL = "https://paper-api.alpaca.markets"
    LIVE_URL = "https://api.alpaca.markets"
    REPORT_URL = os.getenv("REPORT_LINK")
    DB_PATH = os.getenv("DB_PATH", "data/trading.db")

    @classmethod
    def get_auth(cls, mode=None):
        target = mode or cls.MODE
        if target == "LIVE":
            return cls.API_KEY_LIVE, cls.API_SECRET_LIVE, False
        return cls.API_KEY_PAPER, cls.API_SECRET_PAPER, True