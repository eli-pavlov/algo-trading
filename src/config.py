import os

class Config:
    MODE = os.getenv("TRADING_MODE", "PAPER").upper()
    
    # Generic Fallback Source
    _BASE_KEY = os.getenv("APIKEY")
    _BASE_SEC = os.getenv("SECRETKEY")
    
    # Paper Logic
    API_KEY_PAPER = os.getenv("APIKEY_PAPER") or _BASE_KEY
    API_SECRET_PAPER = os.getenv("SECRETKEY_PAPER") or _BASE_SEC
    
    # Live Logic
    API_KEY_LIVE = os.getenv("APIKEY_LIVE") or _BASE_KEY
    API_SECRET_LIVE = os.getenv("SECRETKEY_LIVE") or _BASE_SEC
    
    PAPER_URL = "https://paper-api.alpaca.markets"
    LIVE_URL = "https://api.alpaca.markets"
    DB_PATH = os.getenv("DB_PATH", "data/trading.db")

    @classmethod
    def get_auth(cls, mode=None):
        target = mode or cls.MODE
        if target == "LIVE":
            return cls.API_KEY_LIVE, cls.API_SECRET_LIVE, False
        return cls.API_KEY_PAPER, cls.API_SECRET_PAPER, True