import pandas as pd
import hashlib
import os
import pytz  # Added for Timezone Fix
from requests_cache import CachedSession
from datetime import timedelta
from alpaca_trade_api.rest import TimeFrame
from src.utils.logger import setup_logger
from src.utils.notifications import send_alert
from src.utils.database import log_trade

logger = setup_logger("RSI_Strategy")

# --- Globals ---
PROCESSED_BARS = {}

# --- YFinance Cache ---
CACHE_PATH = os.getenv("YF_CACHE_PATH", "./cache/yfinance")
if os.path.dirname(CACHE_PATH):
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
session = CachedSession(CACHE_PATH, expire_after=timedelta(hours=1))

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).fillna(0)
    loss = (-delta.where(delta < 0, 0)).fillna(0)
    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def fetch_data(symbol, broker):
    # ... (Keep existing fetch_data logic from previous step) ...
    # ... But ensure we return the DF ...
    # (For brevity, assuming standard fetch_data from previous response)
    # Just ensure the DF returned has a DateTimeIndex
    
    # --- INSERTED: Fetch logic placeholder for context ---
    # In your actual file, keep the full fetch_data function I gave you previously.
    # The important fix happens in check_signal below.
    return broker.fetch_data_hybrid(symbol) # Placeholder for your existing logic

def check_signal(symbol, settings, broker):
    try:
        # 1. Fetch Data
        df, source = fetch_data(symbol, broker)
        if df.empty: return

        # --- CRITICAL FIX: TIMEZONE ALIGNMENT ---
        # 1. Ensure Index is TZ-Aware (Default to UTC if missing)
        if df.index.tz is None:
            df.index = df.index.tz_localize('UTC')
        
        # 2. Convert to Market Time (New York)
        # This is required so 'start_day' + '9h30min' offset works correctly
        df_ny = df.index.tz_convert('America/New_York')
        df.index = df_ny

        # 3. Resample with Alignment
        # origin='start_day': Starts bins at midnight local time
        # offset='9h30min': Shifts start to 09:30 AM local time
        agg_logic = {'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}
        tf = settings.get('timeframe', '2h')
        
        df_resampled = df.resample(tf, origin='start_day', offset='9h30min').apply(agg_logic).dropna()

        if len(df_resampled) < 15: return

        # --- FREQUENCY GATE ---
        last_ts = df_resampled.index[-1]
        if PROCESSED_BARS.get(symbol) == last_ts: return
        PROCESSED_BARS[symbol] = last_ts

        # 4. Indicators
        rsi_len = settings.get('rsi_length', 14)
        df_resampled['RSI'] = calculate_rsi(df_resampled['Close'], rsi_len)
        
        current_rsi = df_resampled['RSI'].iloc[-1]
        current_price = df_resampled['Close'].iloc[-1]
        
        logger.info(f"{symbol} | {source} | NY Time: {last_ts} | Price: ${current_price:.2f} | RSI: {current_rsi:.2f}")

        # 5. Signal Logic
        if current_rsi < settings.get('rsi_panic_threshold', 30):
             # ... (Rest of your execution logic: Check positions, Submit Order) ...
             # ... This part remains exactly the same ...
             pass

    except Exception as e:
        logger.error(f"Strategy Error: {e}")