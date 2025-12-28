import time
from src.utils.logger import setup_logger
from src.utils.notifications import send_alert

logger = setup_logger("StopManager")

# Config: 10% Trailing Stop
TRAIL_PCT = 0.10

def update_trailing_stops(broker):
    """
    Iterates through all open positions.
    If price has moved up, cancels the old stop and submits a higher one.
    """
    try:
        positions = broker.api.list_positions()
        if not positions:
            return

        orders = broker.api.list_orders(status='open')
        
        for pos in positions:
            symbol = pos.symbol
            qty = float(pos.qty)
            current_price = float(pos.current_price)
            entry_price = float(pos.avg_entry_price)
            
            # 1. Calculate Theoretical Trailing Stop Price
            # We assume current_price IS the high water mark for simplicity in this loop
            # (A more complex version would track HWM in DB, but this works for active management)
            new_stop_price = round(current_price * (1 - TRAIL_PCT), 2)
            
            # 2. Find Existing Stop Order
            current_stop_order = None
            for o in orders:
                if o.symbol == symbol and o.type == 'stop' and o.side == 'sell':
                    current_stop_order = o
                    break
            
            # 3. Logic: Update if New Stop is HIGHER than Old Stop
            if current_stop_order:
                old_stop_price = float(current_stop_order.stop_price)
                
                # Buffer: Only update if change is significant (> 0.5%) to avoid spamming updates
                if new_stop_price > (old_stop_price * 1.005):
                    logger.info(f"🔄 Updating Stop for {symbol}: ${old_stop_price} -> ${new_stop_price}")
                    
                    try:
                        broker.api.cancel_order(current_stop_order.id)
                        time.sleep(0.5) # Wait for cancel
                        
                        broker.api.submit_order(
                            symbol=symbol,
                            qty=qty,
                            side='sell',
                            type='stop',
                            time_in_force='gtc',
                            stop_price=new_stop_price
                        )
                        
                        send_alert({
                            "EVENT": "TRAILING STOP UPDATE",
                            "Symbol": symbol,
                            "New Stop": f"${new_stop_price}",
                            "Locked Profit": f"{(new_stop_price - entry_price)/entry_price*100:.2f}%"
                        })
                        
                    except Exception as e:
                        logger.error(f"Failed to update stop order for {symbol}: {e}")
            
            else:
                # No Stop Found? (Maybe manual trade or glitch). Create one.
                logger.warning(f"⚠️ No Stop Order found for {symbol}. Creating safety stop at ${new_stop_price}")
                broker.api.submit_order(
                    symbol=symbol,
                    qty=qty,
                    side='sell',
                    type='stop',
                    time_in_force='gtc',
                    stop_price=new_stop_price
                )

    except Exception as e:
        logger.error(f"Stop Manager Error: {e}")