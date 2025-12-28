import yfinance as yf
import pandas as pd
from requests_cache import CachedSession
from datetime import timedelta
from src.utils.logger import setup_logger
from src.utils.notifications import send_alert
from src.utils.database import log_trade

logger = setup_logger("RSI_Strategy")

# Cache Yahoo data to prevent rate limits
# Using /app/cache to map to docker volume
session = CachedSession('/app/cache/yfinance', expire_after=timedelta(hours=1))

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

def check_signal(symbol, settings, broker):
    """
    Checks RSI and executes trades.
    """
    logger.debug(f"Checking {symbol}...")
    
    try:
        # Optimized: Only fetch 20 days.
        # This is enough for 14-period RSI on 2h timeframe (approx 140 bars needed).
        df = yf.download(symbol, period='20d', interval='1h', progress=False, session=session)
        
        if df.empty:
            logger.warning(f"No data fetched for {symbol}")
            return
        
        # Resample
        agg_logic = {
            'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'
        }
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
            
            if broker.get_position(symbol):
                logger.info(f"Signal active ({current_rsi:.2f}), but position held.")
                return

            logger.warning(f"🚨 BUY SIGNAL: {symbol} (RSI {current_rsi:.2f})")
            
            tp_pct = settings.get('take_profit_pct', 0.05)
            sl_pct = settings.get('stop_loss_pct', 0.02)
            
            tp_price = round(current_price * (1 + tp_pct), 2)
            sl_price = round(current_price * (1 - sl_pct), 2)

            order = broker.submit_bracket_order(
                symbol=symbol,
                qty=settings.get('qty', 1),
                side='buy',
                take_profit_price=tp_price,
                stop_loss_price=sl_price
            )

            if order:
                log_trade(symbol, 'buy', settings.get('qty', 1), current_price, "RSI_Panic")
                send_alert({
                    "EVENT": "PANIC BUY",
                    "Symbol": symbol,
                    "Price": f"${current_price}",
                    "RSI": f"{current_rsi:.2f}"
                })

    except Exception as e:
        logger.error(f"Strategy Error on {symbol}: {e}")