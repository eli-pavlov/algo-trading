import streamlit as st
import pandas as pd
import sqlite3
import os
from src.broker import Broker
from src.database import update_status, get_status, DB_PATH

st.set_page_config(page_title="Algo Command Center", layout="wide")
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

# Engine Toggle
engine_on = get_status("engine_running") == "1"
if st.sidebar.button("🛑 STOP ENGINE" if engine_on else "🚀 START ENGINE"):
    update_status("engine_running", "0" if engine_on else "1")
    st.rerun()

# --- MAIN ---
st.title("🛡️ Algo Command Center")
tabs = st.tabs(["📊 Assets", "⚙️ Strategies", "🕹️ Control", "🔍 Debug"])

with tabs[0]:
    st.subheader("Current Holdings")
    try:
        pos = broker.api.list_positions()
        if pos:
            # Display unrealized P/L to see how trades are doing
            data = []
            for p in pos:
                data.append({
                    "Symbol": p.symbol,
                    "Qty": p.qty,
                    "Price": f"${float(p.current_price):.2f}",
                    "Total Value": f"${float(p.market_value):.2f}",
                    "P/L %": f"{float(p.unrealized_plpc)*100:.2f}%"
                })
            st.table(pd.DataFrame(data))
        else:
            st.info("No active positions. Monitoring for signals...")
    except Exception as e:
        st.error(f"Error fetching positions: {e}")

with tabs[1]:
    st.subheader("Optimized Strategy Settings")
    with sqlite3.connect(DB_PATH) as conn:
        df = pd.read_sql("SELECT * FROM strategies", conn)
        if df.empty:
            st.warning("No strategies found. Run analyzer.py to start automated trading.")
        else:
            st.dataframe(df, use_container_width=True)

with tabs[2]:
    st.subheader("🕹️ Manual Override")
    c1, c2, c3 = st.columns(3)
    with c1: m_sym = st.text_input("Ticker", "TSLA").upper()
    with c2: m_qty = st.number_input("Qty", min_value=0.0, value=1.0)
    with c3: m_side = st.selectbox("Side", ["buy", "sell"])
    
    if st.button("Submit Manual Order"):
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "INSERT INTO manual_orders (symbol, qty, side, type) VALUES (?, ?, ?, 'market')",
                (m_sym, m_qty, m_side)
            )
        st.success(f"Queued {m_side} order for {m_sym}")

with tabs[3]:
    st.subheader("System Internals")
    st.write(f"**Database:** `{DB_PATH}`")
    st.write(f"**Host Network:** `Enabled`")
    st.write(f"**Connection Log:**")
    st.code(msg)