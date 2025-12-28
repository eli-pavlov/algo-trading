import yfinance as yf
import pandas as pd
import hashlib
import os
from requests_cache import CachedSession
from datetime import timedelta
from src.utils.logger import setup_logger
from src.utils.notifications import send_alert
from src.utils.database import log_trade

logger = setup_logger("RSI_Strategy")

# Fix: Use environment variable for cache path to support CI/Local/Docker
# Fallback to local './cache' if not running in Docker
CACHE_PATH = os.getenv("YF_CACHE_PATH", "./cache/yfinance")
os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)

session = CachedSession(CACHE_PATH, expire_after=timedelta(hours=1))

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).fillna(0)
    loss = (-delta.where(delta < 0, 0)).fillna(0)
    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def check_signal(symbol, settings, broker):
    logger.debug(f"Checking {symbol}...")
    
    try:
        df = yf.download(symbol, period='30d', interval='1h', progress=False, session=session)
        if df.empty:
            logger.warning(f"No data fetched for {symbol}")
            return
        
        # Resample
        agg_logic = {'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}
        df_resampled = df.resample(settings.get('timeframe', '2h')).apply(agg_logic).dropna()

        # Indicators
        rsi_len = settings.get('rsi_length', 14)
        df_resampled['RSI'] = calculate_rsi(df_resampled['Close'], rsi_len)
        
        last_candle = df_resampled.iloc[-1]
        current_price = last_candle['Close']
        current_rsi = last_candle['RSI']

        logger.info(f"{symbol} | Price: ${current_price:.2f} | RSI: {current_rsi:.2f}")

        # Trigger
        threshold = settings.get('rsi_panic_threshold', 30)
        if current_rsi < threshold:
            
            # 1. Check existing position
            if broker.get_position(symbol):
                logger.info(f"Signal active, but position held.")
                return

            # 2. Check open orders
            if broker.has_open_order(symbol):
                logger.info(f"Signal active, but open order exists.")
                return

            logger.warning(f"🚨 BUY SIGNAL: {symbol} (RSI {current_rsi:.2f})")
            
            tp_pct = settings.get('take_profit_pct', 0.05)
            sl_pct = settings.get('stop_loss_pct', 0.02)
            tp_price = round(current_price * (1 + tp_pct), 2)
            sl_price = round(current_price * (1 - sl_pct), 2)

            # 3. Generate Idempotency ID
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
                    "ID": dedupe_id
                })

    except Exception as e:
        logger.error(f"Strategy Error on {symbol}: {e}")