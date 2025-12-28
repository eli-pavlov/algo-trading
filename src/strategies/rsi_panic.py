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
    """
    # --- METHOD A: ALPACA (Primary) ---
    try:
        # Fetch ~30 days of 1-hour bars (approx 750 hours) to allow valid 2h resampling
        # We use 1-Hour bars and let pandas resample to 2h later
        bars = broker.api.get_bars(
            symbol,
            TimeFrame.Hour,
            limit=1000, 
            adjustment='raw'
        ).df

        if not bars.empty:
            # Alpaca returns lowercase columns (open, high, low, close, volume)
            # We rename them to Match YFinance (Open, High, Low, Close, Volume)
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
            return bars

    except Exception as e:
        logger.warning(f"Alpaca Data failed for {symbol}: {e}. Falling back to Yahoo...")

    # --- METHOD B: YFINANCE (Fallback) ---
    try:
        df = yf.download(symbol, period='30d', interval='1h', progress=False, session=session)
        if not df.empty:
            logger.debug(f"Fetched {len(df)} bars from Yahoo for {symbol}")
            return df
    except Exception as e:
        logger.error(f"Yahoo Data also failed for {symbol}: {e}")
    
    return pd.DataFrame() # Return empty if both fail

def check_signal(symbol, settings, broker):
    logger.debug(f"Checking {symbol}...")
    
    try:
        # 1. Fetch Data (Hybrid)
        df = fetch_data(symbol, broker)
        
        if df.empty:
            logger.warning(f"No data fetched for {symbol} (Source: All Failed)")
            return
        
        # 2. Resample (Standardize 1h data to user timeframe, e.g., 2h)
        # We use the same aggregation logic for both data sources
        agg_logic = {'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}
        
        # Ensure timeframe string is valid for pandas (e.g. "2h" -> "2h")
        tf = settings.get('timeframe', '2h')
        df_resampled = df.resample(tf).apply(agg_logic).dropna()

        if len(df_resampled) < 15:
            logger.warning(f"Not enough bars after resampling for {symbol} (Count: {len(df_resampled)})")
            return

        # 3. Indicators
        rsi_len = settings.get('rsi_length', 14)
        df_resampled['RSI'] = calculate_rsi(df_resampled['Close'], rsi_len)
        
        last_candle = df_resampled.iloc[-1]
        current_price = last_candle['Close']
        current_rsi = last_candle['RSI']

        logger.info(f"{symbol} | Price: ${current_price:.2f} | RSI: {current_rsi:.2f}")

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
            last_ts = df_resampled.index[-1]
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
                    "Source": "Alpaca" if "raw" in str(df.columns) else "Hybrid", # Metadata hint
                    "ID": dedupe_id
                })

    except Exception as e:
        logger.error(f"Strategy Error on {symbol}: {e}")