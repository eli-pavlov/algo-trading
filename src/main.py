# In src/main.py

def process_manual_queue(broker):
    try:
        orders = get_pending_manual_orders()
        for o in orders:
            o_id, sym, qty, side, o_type = o
            ok, msg = broker.submit_order(sym, qty, side, o_type)
            status = 'COMPLETED' if ok else 'FAILED'
            update_manual_order_status(o_id, status)
            
            # REMOVED: if ok: send_trade_notification() 
            # Reason: Dashboard now sends it immediately for better UX.
            # If you add other sources (like a CLI), you might want to add this back conditionally.
            
    except Exception as e:
        print(f"Manual Queue Error: {e}")