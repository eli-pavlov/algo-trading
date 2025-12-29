import streamlit as st
import pandas as pd
import sqlite3
import os
from src.broker import Broker
from src.database import update_status, get_status, DB_PATH

st.set_page_config(page_title="Algo Command Center", layout="wide")
broker = Broker()

# --- SIDEBAR: HEALTH & ACCOUNT ---
st.sidebar.title("📡 System Health")

# API Health and Account Metrics
account_data = broker.get_account_stats()

if "ERROR" in account_data:
    st.sidebar.error("API Status: 🔴 DISCONNECTED")
    st.sidebar.info("Check Alpaca Keys or SSL bypass in broker.py")
    portfolio_val = "$0.00"
    buying_power = "$0.00"
else:
    # Check Market Status
    try:
        clock = broker.api.get_clock()
        health = "🟢 ONLINE" if clock.is_open else "🟡 MARKET CLOSED"
    except Exception:
        health = "🟠 CONNECTED (No Clock)"
    
    st.sidebar.success(f"API Status: {health}")
    portfolio_val = account_data.get('TOTAL_PORTFOLIO', "$0.00")
    buying_power = account_data.get('BUYING_POWER', "$0.00")

st.sidebar.metric("Portfolio Value", portfolio_val)
st.sidebar.metric("Buying Power", buying_power)

# Engine Toggle
engine_on = get_status("engine_running") == "1"
btn_label = "🛑 STOP ENGINE" if engine_on else "🚀 START ENGINE"
if st.sidebar.button(btn_label):
    update_status("engine_running", "0" if engine_on else "1")
    st.rerun()

# --- MAIN UI ---
st.title("🛡️ Algo Command Center")

tab1, tab2, tab3 = st.tabs(["📊 Performance", "⚙️ Strategies", "🕹️ Manual Control"])

with tab1:
    st.subheader("Holdings & Assets")
    try:
        positions = broker.api.list_positions()
        if positions:
            pos_data = []
            for p in positions:
                pos_data.append({
                    "Symbol": p.symbol,
                    "Qty": p.qty,
                    "Avg Entry": p.avg_entry_price,
                    "Current Price": p.current_price,
                    "Unrealized P/L": f"{float(p.unrealized_plpc)*100:.2f}%"
                })
            st.table(pd.DataFrame(pos_data))
        else:
            st.info("No active positions.")
    except Exception:
        st.warning("Could not fetch positions from Alpaca.")

with tab2:
    st.subheader("Active Logic Settings")
    try:
        with sqlite3.connect(DB_PATH) as conn:
            df_strat = pd.read_sql("SELECT * FROM strategies", conn)
            if not df_strat.empty:
                st.dataframe(df_strat, use_container_width=True)
            else:
                st.info("No strategies found in database. Run analyzer.py to populate.")
    except Exception:
        st.error("Database connection failed.")

with tab3:
    st.subheader("Manual Override Console")
    col1, col2, col3, col4 = st.columns(4)
    with col1: m_sym = st.text_input("Symbol (e.g. TSLA)", "TSLA")
    with col2: m_qty = st.number_input("Quantity", min_value=0.1, value=1.0)
    with col3: m_side = st.selectbox("Action", ["buy", "sell"])
    with col4: m_type = st.selectbox("Order Type", ["market", "limit"])
    
    if st.button("🔥 SEND MANUAL ORDER"):
        try:
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute(
                    "INSERT INTO manual_orders (symbol, qty, side, type) VALUES (?,?,?,?)",
                    (m_sym.upper(), m_qty, m_side, m_type)
                )
            st.success(f"SUCCESS: {m_side.upper()} order for {m_sym} queued in system.")
        except Exception as e:
            st.error(f"Failed to queue order: {e}")