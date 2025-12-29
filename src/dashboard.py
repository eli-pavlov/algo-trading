import streamlit as st
import pandas as pd
import sqlite3
import time
from src.broker import Broker
from src.database import get_status, update_status, DB_PATH

st.set_page_config(page_title="Algo Command Center", layout="wide", page_icon="🛡️")

# Initialize Broker
broker = Broker()

# --- HEADER: Market Clock ---
st.markdown(f"### 🕒 {broker.get_market_clock()}")
st.markdown("---")

# --- TOP ROW: Portfolio Performance ---
col1, col2, col3, col4, col5 = st.columns(5)
acc = broker.get_account_stats()
hist = broker.get_portfolio_history_stats()

with col1: st.metric("Total Equity", f"${acc.get('Equity', 0):,.2f}")
with col2: st.metric("Day P/L", hist.get('1D', 'N/A'))
with col3: st.metric("Week P/L", hist.get('1W', 'N/A'))
with col4: st.metric("Month P/L", hist.get('1M', 'N/A'))
with col5: st.metric("Year P/L", hist.get('1A', 'N/A'))

# --- MAIN TABS ---
tab_assets, tab_strat, tab_manual, tab_debug = st.tabs(["📊 Assets & Orders", "⚙️ Strategies", "🕹️ Manual Control", "🔍 Debug"])

# 1. ASSETS TAB
with tab_assets:
    st.subheader("Active Holdings & Open Orders")
    try:
        positions = broker.api.list_positions()
        if positions:
            for p in positions:
                with st.expander(f"{p.symbol} | {p.qty} shares | P/L: ${float(p.unrealized_pl):.2f} ({float(p.unrealized_plpc)*100:.2f}%)"):
                    c1, c2, c3, c4 = st.columns(4)
                    c1.write(f"**Current Price:** ${float(p.current_price):.2f}")
                    c2.write(f"**Avg Entry:** ${float(p.avg_entry_price):.2f}")
                    c3.write(f"**Market Value:** ${float(p.market_value):.2f}")
                    c4.write(f"**Day P/L:** ${float(p.unrealized_intraday_pl):.2f}")
                    
                    # Fetch Open Orders for this symbol
                    open_orders = broker.get_orders_for_symbol(p.symbol)
                    st.write("---")
                    st.write("**⚠️ Active Orders (Stop Loss / Take Profit):**")
                    if open_orders:
                        for o in open_orders:
                            st.code(o)
                    else:
                        st.caption("No active open orders.")
        else:
            st.info("No active positions.")
    except Exception as e:
        st.error(f"Error fetching assets: {e}")

# 2. STRATEGIES TAB
with tab_strat:
    st.subheader("Strategy Parameters")
    with sqlite3.connect(DB_PATH) as conn:
        try:
            df = pd.read_sql("SELECT * FROM strategies", conn)
            st.dataframe(df, use_container_width=True)
        except:
            st.warning("Database empty or locked.")

# 3. MANUAL CONTROL TAB (Enhanced)
with tab_manual:
    st.subheader("🕹️ Advanced Order Entry")
    
    c_sym, c_qty, c_side = st.columns(3)
    sym = c_sym.text_input("Symbol", "TSLA").upper()
    qty = c_qty.number_input("Quantity", min_value=0.1, value=1.0)
    side = c_side.selectbox("Side", ["buy", "sell"])
    
    c_type, c_param = st.columns([1, 2])
    type = c_type.selectbox("Order Type", ["market", "limit", "stop", "stop_limit", "trailing_stop"])
    
    # Dynamic inputs based on order type
    limit_px, stop_px, trail_pct = None, None, None
    if type == "limit":
        limit_px = c_param.number_input("Limit Price", min_value=0.01)
    elif type == "stop":
        stop_px = c_param.number_input("Stop Price", min_value=0.01)
    elif type == "stop_limit":
        col_sl1, col_sl2 = c_param.columns(2)
        stop_px = col_sl1.number_input("Stop Price", min_value=0.01)
        limit_px = col_sl2.number_input("Limit Price", min_value=0.01)
    elif type == "trailing_stop":
        trail_pct = c_param.number_input("Trail Percent (%)", min_value=0.1, max_value=100.0)

    if st.button("🚀 SUBMIT ORDER", type="primary"):
        with st.spinner("Transmitting to Alpaca..."):
            success, msg = broker.submit_manual_order(sym, qty, side, type, limit_px, stop_px, trail_pct)
            if success:
                st.success(f"✅ {msg}")
                time.sleep(1) # Wait for Alpaca to process
                st.rerun()    # Force UI Refresh
            else:
                st.error(f"❌ {msg}")

# 4. DEBUG TAB
with tab_debug:
    conn_status, conn_msg = broker.test_connection()
    st.write(f"**Connection:** {conn_msg}")
    
    engine_on = get_status("engine_running") == "1"
    btn_txt = "🛑 STOP AUTOMATED ENGINE" if engine_on else "♻️ START AUTOMATED ENGINE"
    if st.button(btn_txt):
        update_status("engine_running", "0" if engine_on else "1")
        st.rerun()

# --- SIDEBAR INFO ---
st.sidebar.title("Overview")
st.sidebar.info(f"**Buying Power:** ${acc.get('Power', 0):,.2f}")
st.sidebar.info(f"**Cash:** ${acc.get('Cash', 0):,.2f}")
st.sidebar.caption("Auto-refreshing on interaction")