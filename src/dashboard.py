import streamlit as st
import pandas as pd
import sqlite3
import os
from src.broker import Broker
from src.database import update_status, get_status, DB_PATH

st.set_page_config(page_title="Algo UI", layout="wide")
broker = Broker()

# --- SIDEBAR ---
st.sidebar.title("📡 System Health")
connected, msg = broker.test_connection()

if connected:
    st.sidebar.success("API Status: 🟢 ONLINE")
    acc = broker.get_account_stats()
    st.sidebar.metric("Portfolio", acc.get('TOTAL_PORTFOLIO', "$0"))
    st.sidebar.metric("Buying Power", acc.get('BUYING_POWER', "$0"))
else:
    st.sidebar.error("API Status: 🔴 DISCONNECTED")
    st.sidebar.code(msg)

if st.sidebar.button("Toggle Engine"):
    curr = get_status("engine_running")
    update_status("engine_running", "0" if curr == "1" else "1")
    st.rerun()

# --- MAIN ---
st.title("🛡️ Algo Command Center")
tabs = st.tabs(["📊 Assets", "⚙️ Strategies", "🕹️ Control", "🔍 Debug"])

with tabs[0]:
    st.subheader("Holdings")
    pos = broker.api.list_positions()
    if pos:
        st.table(pd.DataFrame([{"Sym": p.symbol, "Qty": p.qty, "Price": p.current_price} for p in pos]))
    else:
        st.info("No positions.")

with tabs[1]:
    st.subheader("Logic Settings")
    with sqlite3.connect(DB_PATH) as conn:
        df = pd.read_sql("SELECT * FROM strategies", conn)
        st.dataframe(df, use_container_width=True)

with tabs[3]:
    st.subheader("Debug Console")
    st.write(f"**Target URL:** `{broker.base_url}/v2/account`")
    st.write(f"**API Key Present:** `{'✅' if broker.api_key else '❌'}`")
    st.write("---")
    st.write("**Last Error Message:**")
    st.error(msg)