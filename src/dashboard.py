import streamlit as st
import pandas as pd
import sqlite3
import os
import plotly.express as px
from src.broker import Broker
from src.database import update_status, get_status

st.set_page_config(page_title="Algo Command Center", layout="wide")
DB_PATH = os.getenv("DB_PATH", "data/trading.db")
broker = Broker()

# --- SIDEBAR: HEALTH & ACCOUNT ---
st.sidebar.title("📡 System Health")

# API Health Check
try:
    clock = broker.api.get_clock()
    health = "🟢 ONLINE" if clock.is_open else "🟡 MARKET CLOSED"
    update_status("api_health", health)
except:
    health = "🔴 API ERROR"

st.sidebar.metric("API Status", health)

# Account Stats
stats = broker.get_account_stats()
st.sidebar.metric("Portfolio Value", stats['TOTAL_PORTFOLIO'])
st.sidebar.metric("Buying Power", stats['BUYING_POWER'])

# Engine Toggle
engine_on = get_status("engine_running") == "1"
if st.sidebar.button("🛑 STOP ENGINE" if engine_on else "🚀 START ENGINE"):
    update_status("engine_running", "0" if engine_on else "1")
    st.rerun()

# --- MAIN UI ---
st.title("🛡️ Algo Command Center")

tab1, tab2, tab3 = st.tabs(["📈 Performance", "⚙️ Strategies", "🕹️ Manual Control"])

with tab1:
    st.subheader("Account Growth")
    # (Existing Plotly Code here)

with tab2:
    st.subheader("Active Logic Settings")
    with sqlite3.connect(DB_PATH) as conn:
        df_strat = pd.read_sql("SELECT * FROM strategies", conn)
        st.dataframe(df_strat, use_container_width=True)

with tab3:
    st.subheader("Manual Order Entry")
    col1, col2, col3, col4 = st.columns(4)
    with col1: sym = st.text_input("Symbol", "TSLA")
    with col2: qty = st.number_input("Qty", min_value=0.1, value=1.0)
    with col3: side = st.selectbox("Side", ["buy", "sell"])
    with col4: o_type = st.selectbox("Type", ["market", "limit"])
    
    if st.button("Execute Manual Trade"):
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("INSERT INTO manual_orders (symbol, qty, side, type) VALUES (?,?,?,?)",
                         (sym, qty, side, o_type))
        st.success(f"Order for {sym} queued!")