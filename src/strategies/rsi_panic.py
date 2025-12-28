import yfinance as yf
import pandas as pd
import hashlib
import os
from requests_cache import CachedSession
from datetime import timedelta, datetime
from alpaca_trade_api.rest import TimeFrame
from src.utils.logger import setup_logger
from src.utils.notifications import send_alert
from src.utils.database import log_trade

logger = setup_logger("RSI_Strategy")

# --- Globals for State Management ---
# Stores the timestamp of the last processed candle per symbol
# to prevent re-running logic on the same candle every minute.
PROCESSED_BARS = {}

# --- YFinance Cache Setup (Fallback) ---
CACHE_PATH = os.getenv("YF_CACHE_PATH", "./cache/yfinance")
cache_dir = os.path.dirname(CACHE_PATH)
if cache_dir:
    os.makedirs(cache_dir, exist_ok=True)

session = CachedSession(CACHE_PATH, expire_after=timedelta(hours=1))

def calculate_rsi(series, period=14):
    """
    Native RSI calculation (Wilder's Smoothing).
    """
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).fillna(0)
    loss = (-delta.where(delta < 0, 0)).fillna(0)

    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def fetch_data(symbol, broker):
    """
    Hybrid Data Fetcher:
    1. Try Alpaca (Primary - IEX Data)
    2. Fallback to Yahoo Finance (Backup)
    
    Returns:
        tuple: (DataFrame, source_string)
    """
    # --- METHOD A: ALPACA (Primary) ---
    try:
        # Fetch ~60 days of data to allow resampling
        bars = broker.api.get_bars(
            symbol,
            TimeFrame.Hour,
            limit=1000, 
            adjustment='raw'
        ).df

        if not bars.empty:
            # CRITICAL FIX: Handle MultiIndex return from Alpaca
            # If indexed by (symbol, timestamp), flatten to just timestamp
            if isinstance(bars.index, pd.MultiIndex):
                bars = bars.xs(symbol, level=0)

            # Alpaca returns lowercase columns -> Rename to Title Case
            bars.rename(columns={
                'open': 'Open', 
                'high': 'High', 
                'low': 'Low', 
                'close': 'Close', 
                'volume': 'Volume'
            }, inplace=True)
            
            # Ensure index is timezone aware (Alpaca usually is UTC)
            if bars.index.tz is None:
                bars.index = bars.index.tz_localize('UTC')
                
            logger.debug(f"Fetched {len(bars)} bars from Alpaca for {symbol}")
            return bars, "Alpaca"

    except Exception as e:
        logger.warning(f"Alpaca Data failed for {symbol}: {e}. Falling back to Yahoo...")

    # --- METHOD B: YFINANCE (Fallback) ---
    try:
        df = yf.download(symbol, period='60d', interval='1h', progress=False, session=session)
        if not df.empty:
            logger.debug(f"Fetched {len(df)} bars from Yahoo for {symbol}")
            return df, "Yahoo"
    except Exception as e:
        logger.error(f"Yahoo Data also failed for {symbol}: {e}")
    
    return pd.DataFrame(), "None"

def check_signal(symbol, settings, broker):
    """
    Core Logic:
    1. Check if we already processed this candle (Frequency Gate).
    2. Fetch Data (Hybrid).
    3. Resample to 2h/4h.
    4. Calculate RSI.
    5. Execute Trade if Panic detected.
    """
    logger.debug(f"Checking {symbol}...")
    
    try:
        # 1. Fetch Data (Returns DF and Source)
        df, source = fetch_data(symbol, broker)
        
        if df.empty:
            logger.warning(f"No data fetched for {symbol} (Source: All Failed)")
            return
        
        # 2. Resample (Standardize 1h data to user timeframe, e.g., 2h)
        agg_logic = {'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}
        tf = settings.get('timeframe', '2h')
        
        # Resample and drop incomplete bars if necessary, though dropna handles empty intervals
        df_resampled = df.resample(tf).apply(agg_logic).dropna()

        if len(df_resampled) < 15:
            logger.warning(f"Not enough bars after resampling for {symbol} (Count: {len(df_resampled)})")
            return

        # --- FREQUENCY GATE ---
        # Only process logic if we have a NEW bar.
        # This prevents the bot from spamming calculations every minute on a 2-hour candle.
        last_ts = df_resampled.index[-1]
        
        if PROCESSED_BARS.get(symbol) == last_ts:
            # We already ran logic for this specific candle timestamp
            logger.debug(f"Skipping {symbol}: Candle {last_ts} already processed.")
            return
        
        # Update cache
        PROCESSED_BARS[symbol] = last_ts

        # 3. Indicators
        rsi_len = settings.get('rsi_length', 14)
        df_resampled['RSI'] = calculate_rsi(df_resampled['Close'], rsi_len)
        
        last_candle = df_resampled.iloc[-1]
        current_price = last_candle['Close']
        current_rsi = last_candle['RSI']

        logger.info(f"{symbol} | Source: {source} | Price: ${current_price:.2f} | RSI: {current_rsi:.2f}")

        # 4. Trigger Logic
        threshold = settings.get('rsi_panic_threshold', 30)
        
        if current_rsi < threshold:
            
            # Check existing position
            if broker.get_position(symbol):
                logger.info(f"Signal active ({current_rsi:.2f}), but position held.")
                return

            # Check open orders
            if broker.has_open_order(symbol):
                logger.info(f"Signal active, but open order exists.")
                return

            logger.warning(f"🚨 BUY SIGNAL: {symbol} (RSI {current_rsi:.2f})")
            
            tp_pct = settings.get('take_profit_pct', 0.05)
            sl_pct = settings.get('stop_loss_pct', 0.02)
            tp_price = round(current_price * (1 + tp_pct), 2)
            sl_price = round(current_price * (1 - sl_pct), 2)

            # Idempotency ID
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
                log_trade(
                    symbol=symbol, 
                    side='buy', 
                    qty=settings.get('qty', 1), 
                    price=current_price, 
                    strategy="RSI_Panic",
                    client_order_id=dedupe_id
                )
                send_alert({
                    "EVENT": "PANIC BUY",
                    "Symbol": symbol,
                    "Price": f"${current_price}",
                    "RSI": f"{current_rsi:.2f}",
                    "Source": source, # Now uses the actual tracked source
                    "ID": dedupe_id
                })

    except Exception as e:
        logger.error(f"Strategy Error on {symbol}: {e}")