import streamlit as st
import pandas as pd
import sqlite3
import time
import json
from src.broker import Broker
from src.database import get_status, update_status, delete_strategy, DB_PATH

# 1. Page Config
st.set_page_config(page_title="Algo Command Center", layout="wide", page_icon="🛡️")

# 2. Broker Init
broker = Broker()
conn_status, conn_msg = broker.test_connection()

# 3. Sidebar: The New "Overview" Home
with st.sidebar:
    st.title("📡 System Overview")
    
    if conn_status:
        st.success("API Status: 🟢 ONLINE")
    else:
        st.error(f"API Status: 🔴 DISCONNECTED\n{conn_msg}")
        
    st.markdown("---")
    
    # Live Account Metrics
    acc = broker.get_account_stats()
    c1, c2 = st.columns(2)
    c1.metric("Buying Power", f"${acc.get('Power', 0):,.2f}")
    c2.metric("Cash", f"${acc.get('Cash', 0):,.2f}")
    
    st.markdown("---")
    st.subheader("📈 Performance")
    
    # Portfolio History
    hist = broker.get_portfolio_history_stats()
    st.metric("Total Equity", f"${acc.get('Equity', 0):,.2f}")
    
    # Compact Grid for Timeframes
    h1, h2 = st.columns(2)
    h1.metric("1 Day", hist.get('1D', 'N/A'))
    h2.metric("1 Week", hist.get('1W', 'N/A'))
    h3, h4 = st.columns(2)
    h3.metric("1 Month", hist.get('1M', 'N/A'))
    h4.metric("1 Year", hist.get('1A', 'N/A'))
    
    st.markdown("---")
    
    # Engine Control
    engine_on = get_status("engine_running") == "1"
    btn_label = "🛑 STOP ENGINE" if engine_on else "🚀 START ENGINE"
    if st.button(btn_label, use_container_width=True):
        update_status("engine_running", "0" if engine_on else "1")
        st.rerun()

# 4. Main Header: Market Clock
clock_msg = broker.get_market_clock()
if "🟢" in clock_msg:
    st.info(f"### {clock_msg}")
else:
    st.warning(f"### {clock_msg}")

# 5. Main Tabs
tab_assets, tab_strat, tab_manual, tab_debug = st.tabs([
    "📊 Assets & Performance", 
    "⚙️ Strategies", 
    "🕹️ Manual Control", 
    "🔍 Debug"
])

# --- TAB 1: ASSETS ---
with tab_assets:
    st.subheader("Holdings & Active Orders")
    try:
        positions = broker.api.list_positions()
        if positions:
            for p in positions:
                # Custom calculation for day P/L vs Total P/L
                pl_day = float(p.unrealized_intraday_pl)
                pl_total = float(p.unrealized_pl)
                
                # Visual Expander
                with st.expander(f"{p.symbol} | {p.qty} shares | Total P/L: ${pl_total:.2f}"):
                    # Metrics Grid
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("Current Price", f"${float(p.current_price):.2f}")
                    m2.metric("Avg Entry", f"${float(p.avg_entry_price):.2f}")
                    m3.metric("Day P/L", f"${pl_day:.2f}", delta=pl_day)
                    m4.metric("Total P/L", f"${pl_total:.2f}", delta=pl_total)
                    
                    st.divider()
                    
                    # Open Orders Section
                    st.markdown("**⚠️ Active Stops & Limits**")
                    open_orders = broker.get_orders_for_symbol(p.symbol)
                    if open_orders:
                        for o in open_orders:
                            st.code(o, language="text")
                    else:
                        st.caption("No active orders for this symbol.")
        else:
            st.info("No active positions.")
    except Exception as e:
        st.error(f"Error fetching assets: {e}")

# --- TAB 2: STRATEGIES (VISUAL UPDATE) ---
with tab_strat:
    st.subheader("Active Bot Strategies")
    st.caption("Strategies define entry rules. Exits are handled by Bracket Orders (TP/SL).")
    
    with sqlite3.connect(DB_PATH) as conn:
        try:
            # Fetch raw data
            df = pd.read_sql("SELECT * FROM strategies", conn)
            
            if not df.empty:
                # Iterate rows to create custom UI
                for index, row in df.iterrows():
                    with st.container():
                        # Layout: Symbol Name (Small) | Params (Wide) | Delete (Small)
                        c1, c2, c3 = st.columns([1, 5, 1])
                        
                        # Column 1: Symbol
                        c1.markdown(f"## {row['symbol']}")
                        
                        # Column 2: Formatted Metrics
                        try:
                            # Parse JSON params
                            p = json.loads(row['params'])
                            
                            # Create 4 mini-columns for the stats
                            p1, p2, p3, p4 = c2.columns(4)
                            
                            p1.metric("RSI Limit", p.get('rsi_trend', 'N/A'))
                            p2.metric("ADX Min", p.get('adx_trend', 'N/A'))
                            
                            # Convert decimals to percentages
                            tp_pct = p.get('target', 0) * 100
                            sl_pct = p.get('stop', 0) * 100
                            
                            # Color code: TP Green, SL Red (using standard delta logic)
                            p3.metric("Take Profit", f"{tp_pct:.1f}%")
                            p4.metric("Stop Loss", f"{sl_pct:.1f}%")
                            
                        except Exception:
                            c2.warning("Invalid Parameters Format")
                        
                        # Column 3: Delete Button
                        if c3.button("🗑️ Remove", key=f"del_{row['symbol']}", type="primary"):
                            delete_strategy(row['symbol'])
                            st.toast(f"Removed {row['symbol']} from strategies.")
                            time.sleep(1)
                            st.rerun()
                        
                        st.divider()
            else:
                st.warning("Strategy database is empty. Run the Analyzer/Scanner to add stocks.")
        except Exception as e:
            st.error(f"Error loading strategies: {e}")

# --- TAB 3: MANUAL CONTROL ---
with tab_manual:
    st.subheader("🕹️ Place Trade")
    
    with st.form("manual_order_form"):
        c1, c2, c3 = st.columns(3)
        sym = c1.text_input("Symbol", "TSLA").upper()
        qty = c2.number_input("Qty", min_value=0.1, value=1.0)
        side = c3.selectbox("Side", ["buy", "sell"])
        
        c4, c5 = st.columns(2)
        type = c4.selectbox("Order Type", ["market", "limit", "stop", "stop_limit", "trailing_stop"])
        
        # Dynamic inputs logic would go here, but forms require static layout
        # We put all potential inputs in one row for simplicity in the form
        limit_px = c5.number_input("Limit Price (Optional)", min_value=0.0)
        stop_px = c5.number_input("Stop Price (Optional)", min_value=0.0)
        trail_pct = c5.number_input("Trail % (Optional)", min_value=0.0)
        
        submitted = st.form_submit_button("🚀 Submit Order", type="primary")
        
        if submitted:
            # Filter inputs based on type
            l_px = limit_px if type in ['limit', 'stop_limit'] else None
            s_px = stop_px if type in ['stop', 'stop_limit'] else None
            t_pct = trail_pct if type == 'trailing_stop' else None

            success, msg = broker.submit_manual_order(sym, qty, side, type, l_px, s_px, t_pct)
            
            if success:
                st.success(f"✅ {msg}")
                # REFRESH LOGIC: Wait 1s for Alpaca, then reload
                with st.spinner("Refreshing Portfolio..."):
                    time.sleep(1) 
                    st.rerun()
            else:
                st.error(f"❌ {msg}")

# --- TAB 4: DEBUG ---
with tab_debug:
    st.write("System Status:")
    st.json({
        "DB Path": DB_PATH,
        "Connected": conn_status,
        "Engine Running": engine_on,
        "Last API Message": conn_msg
    })