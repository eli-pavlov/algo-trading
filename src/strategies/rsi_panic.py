import yfinance as yf
import pandas as pd
from requests_cache import CachedSession
from datetime import timedelta
from src.utils.logger import setup_logger
from src.utils.notifications import send_alert
from src.utils.database import log_trade  # <--- NEW DEPENDENCY

logger = setup_logger("RSI_Strategy")

# Cache Yahoo data for 1 hour to prevent rate limits during frequent restarts
session = CachedSession('yfinance.cache', expire_after=timedelta(hours=1))

def calculate_rsi(series, period=14):
    """
    Native RSI calculation (Wilder's Smoothing) to avoid heavy library dependencies.
    """
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).fillna(0)
    loss = (-delta.where(delta < 0, 0)).fillna(0)

    # Use exponential weighted moving average (Wilder's method)
    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def check_signal(symbol, settings, broker):
    """
    Main logic: Checks RSI and executes bracket trades if conditions met.
    """
    logger.debug(f"Checking {symbol}...")
    
    try:
        # 1. Fetch History (Need ~60 days of 1h data to resample accurately)
        # We use '1h' base data because it's granular enough to resample into 2h, 4h, etc.
        df = yf.download(symbol, period='60d', interval='1h', progress=False, session=session)
        
        if df.empty:
            logger.warning(f"No data fetched for {symbol}")
            return
        
        # 2. Resample to the Strategy Timeframe (e.g., '2h')
        # Logic: Open=First, High=Max, Low=Min, Close=Last, Volume=Sum
        agg_logic = {
            'Open': 'first', 
            'High': 'max', 
            'Low': 'min', 
            'Close': 'last', 
            'Volume': 'sum'
        }
        df_resampled = df.resample(settings['timeframe']).apply(agg_logic).dropna()

        # 3. Calculate Indicators
        df_resampled['RSI'] = calculate_rsi(df_resampled['Close'], settings['rsi_length'])
        
        # Get the latest completed candle
        last_candle = df_resampled.iloc[-1]
        current_price = last_candle['Close']
        current_rsi = last_candle['RSI']

        logger.info(f"{symbol} | Price: ${current_price:.2f} | RSI: {current_rsi:.2f}")

        # 4. Check Trigger (RSI < Panic Threshold)
        if current_rsi < settings['rsi_panic_threshold']:
            
            # Safety Check: Do not buy if we already have a position
            if broker.get_position(symbol):
                logger.info(f"Signal active (RSI {current_rsi:.2f}), but position already exists for {symbol}.")
                return

            logger.warning(f"🚨 BUY SIGNAL DETECTED: {symbol} (RSI {current_rsi:.2f})")
            
            # Calculate Bracket Prices (Take Profit / Stop Loss)
            tp_price = round(current_price * (1 + settings['take_profit_pct']), 2)
            sl_price = round(current_price * (1 - settings['stop_loss_pct']), 2)

            # 5. Execute Trade
            order = broker.submit_bracket_order(
                symbol=symbol,
                qty=settings['qty'],
                side='buy',
                take_profit_price=tp_price,
                stop_loss_price=sl_price
            )

            # 6. Log & Notify
            if order:
                # Save to Local DB (Audit Trail)
                log_trade(
                    symbol=symbol, 
                    side='buy', 
                    qty=settings['qty'], 
                    price=current_price, 
                    strategy="RSI_Panic"
                )

                # Send Webhook Alert (Slack/Discord)
                send_alert({
                    "EVENT": "PANIC BUY EXECUTED",
                    "Symbol": symbol,
                    "Entry Price": f"${current_price}",
                    "RSI": f"{current_rsi:.2f}",
                    "Take Profit": f"${tp_price}",
                    "Stop Loss": f"${sl_price}"
                })

    except Exception as e:
        logger.error(f"Strategy Error on {symbol}: {e}")