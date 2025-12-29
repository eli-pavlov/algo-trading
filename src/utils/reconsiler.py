import sqlite3
import pandas as pd
import os
import time
from src.brokers.alpaca_api import AlpacaClient
from src.utils.logger import setup_logger

logger = setup_logger("Reconciler")
DB_PATH = os.getenv("DB_PATH", "/app/data/trading.db")

def reconcile_trades():
    broker = AlpacaClient()
    
    # 1. Fetch recently closed orders from Alpaca
    # Limit 50 covers the last few active periods comfortably
    alpaca_orders = broker.api.list_orders(status='closed', limit=100)
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # 2. Fetch our DB trades that haven't been reconciled yet
    # (Where price_filled is NULL)
    c.execute("SELECT client_order_id, symbol, price_requested FROM trades WHERE price_filled IS NULL")
    open_logs = c.fetchall()
    
    updated_count = 0
    total_slippage_pct = []
    
    for row in open_logs:
        client_oid, symbol, price_req = row
        
        # Find matching Alpaca order
        # We match using the 'client_order_id' we generated
        match = next((o for o in alpaca_orders if o.client_order_id == client_oid), None)
        
        if match and match.filled_at:
            real_price = float(match.filled_avg_price)
            filled_qty = float(match.filled_qty)
            
            # Calculate Slippage
            # (Real - Req) / Req
            slippage_amt = real_price - price_req
            slippage_pct = (slippage_amt / price_req) * 100
            
            # Update DB
            c.execute("""
                UPDATE trades 
                SET price_filled = ?, 
                    slippage = ?, 
                    qty = ?
                WHERE client_order_id = ?
            """, (real_price, slippage_pct, filled_qty, client_oid))
            
            logger.info(f"✅ Reconciled {symbol}: Req ${price_req:.2f} -> Fill ${real_price:.2f} (Slip: {slippage_pct:.4f}%)")
            
            updated_count += 1
            total_slippage_pct.append(abs(slippage_pct))
    
    conn.commit()
    conn.close()
    
    if updated_count > 0:
        avg_slip = sum(total_slippage_pct) / len(total_slippage_pct)
        logger.info(f"📊 BATCH REPORT: {updated_count} trades updated.")
        logger.info(f"⚠️ AVG SLIPPAGE: {avg_slip:.4f}% (Use this to tune your backtest!)")
    else:
        logger.info("No new trades to reconcile.")

if __name__ == "__main__":
    reconcile_trades()