import pandas as pd
import hashlib
import os
import pytz
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
    """
    Hybrid Fetcher: Tries Alpaca first, falls back to Yahoo.
    Returns (DataFrame, Source_String)
    """
    # ... (Same fetch logic as before, abbreviated for clarity) ...
    # Ensure this uses the full logic provided in previous steps
    # For now, we assume the broker wrapper handles the heavy lifting
    try:
        # Try Alpaca directly for 1h bars
        bars = broker.api.get_bars(symbol, TimeFrame.Hour, limit=1000, adjustment='raw').df
        if not bars.empty:
            if isinstance(bars.index, pd.MultiIndex):
                bars = bars.xs(symbol, level=0)
            bars.rename(columns={'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'volume': 'Volume'}, inplace=True)
            return bars, "Alpaca"
    except:
        pass
        
    try:
        df = yf.download(symbol, period='60d', interval='1h', progress=False, session=session)
        return df, "Yahoo"
    except:
        return pd.DataFrame(), "None"

def check_market_open(broker):
    """
    Checks if the market is currently open.
    Returns True/False.
    """
    try:
        clock = broker.api.get_clock()
        return clock.is_open
    except Exception as e:
        logger.error(f"Failed to get market clock: {e}")
        # Fail safe: Default to False to avoid accidental OOH trading
        return False

def check_signal(symbol, settings, broker):
    try:
        # 1. MARKET HOURS CHECK (Crucial for Alpaca)
        if not check_market_open(broker):
            logger.debug("Market is closed. Skipping trade checks.")
            return

        # 2. Fetch Data
        df, source = fetch_data(symbol, broker)
        if df.empty: return

        # 3. Timezone Alignment (US/Eastern)
        if df.index.tz is None:
            df.index = df.index.tz_localize('UTC')
        df.index = df.index.tz_convert('America/New_York')

        # 4. Resample to 2h (Aligned to 09:30 ET)
        agg_logic = {'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}
        tf = settings.get('timeframe', '2h')
        
        df_resampled = df.resample(tf, origin='start_day', offset='9h30min').apply(agg_logic).dropna()
        if len(df_resampled) < 15: return

        # 5. Frequency Gate
        last_ts = df_resampled.index[-1]
        if PROCESSED_BARS.get(symbol) == last_ts: return
        PROCESSED_BARS[symbol] = last_ts

        # 6. Indicators (Using DEEP TUNED Values)
        # Force the settings if not provided in YAML
        rsi_len = settings.get('rsi_length', 7) 
        rsi_limit = settings.get('rsi_panic_threshold', 30) # Default to 30 (Champion)
        
        df_resampled['RSI'] = calculate_rsi(df_resampled['Close'], rsi_len)
        current_rsi = df_resampled['RSI'].iloc[-1]
        current_price = df_resampled['Close'].iloc[-1]
        
        logger.info(f"{symbol} | {source} | RSI: {current_rsi:.2f}")

        # 7. Signal Logic
        if current_rsi < rsi_limit:
            
            # Check existing position/orders
            if broker.get_position(symbol) or broker.has_open_order(symbol):
                return

            logger.warning(f"🚨 BUY SIGNAL: {symbol} @ {current_price:.2f}")
            
            # --- ORDER LOGIC (ALIGNED WITH ALPACA RULES) ---
            # We use a Bracket Order (Market Entry + Stop Loss + Take Profit)
            # This ONLY works during Market Hours (which we checked at step 1)
            
            # Trailing Stop Math (10%)
            trail_pct = 0.10
            # Note: Alpaca API does not support 'Trailing Stop' as a leg in a Bracket Order easily.
            # We use a standard STOP LOSS for safety. 
            # The 'Trailing' logic must be managed by the bot updating the stop price, 
            # OR we use a simple 'Take Profit' and accept we might miss the moonshot.
            # PRO FIX: Use a wide Take Profit (50%) and a tight Stop Loss (10%).
            
            sl_price = round(current_price * (1 - 0.10), 2)
            tp_price = round(current_price * (1 + 0.50), 2) # Moonshot target

            raw_id = f"RSI-{symbol}-{int(last_ts.timestamp())}"
            dedupe_id = hashlib.md5(raw_id.encode()).hexdigest()

            order = broker.submit_bracket_order(
                symbol=symbol,
                qty=settings.get('qty', 1),
                side='buy',
                take_profit_price=tp_price,
                stop_loss_price=sl_price,
                client_order_id=dedupe_id
            )

            if order:
                log_trade(symbol, 'buy', settings.get('qty', 1), current_price, "RSI_Moonshot", dedupe_id)
                send_alert({
                    "EVENT": "MOONSHOT ENTRY",
                    "Symbol": symbol,
                    "Price": f"${current_price}",
                    "RSI": f"{current_rsi:.2f}",
                    "Stop": f"${sl_price}",
                    "Target": f"${tp_price}",
                    "Source": source
                })

    except Exception as e:
        logger.error(f"Strategy Error: {e}")