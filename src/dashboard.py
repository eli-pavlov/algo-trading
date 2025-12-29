import streamlit as st
import pandas as pd
import sqlite3
import os
from src.broker import Broker
from src.database import update_status, get_status, DB_PATH

st.set_page_config(page_title="Algo Command Center", layout="wide")
broker = Broker()

# --- SIDEBAR: HEALTH ---
st.sidebar.title("📡 System Health")
is_connected, conn_msg = broker.test_connection()

if is_connected:
    st.sidebar.success("API Status: 🟢 ONLINE")
    stats = broker.get_account_stats()
    st.sidebar.metric("Portfolio Value", stats.get('TOTAL_PORTFOLIO', "$0.00"))
    st.sidebar.metric("Buying Power", stats.get('BUYING_POWER', "$0.00"))
else:
    st.sidebar.error("API Status: 🔴 DISCONNECTED")
    st.sidebar.warning(f"Error: {conn_msg[:50]}...")

# Engine Toggle
engine_on = get_status("engine_running") == "1"
if st.sidebar.button("🛑 STOP ENGINE" if engine_on else "🚀 START ENGINE"):
    update_status("engine_running", "0" if engine_on else "1")
    st.rerun()

# --- MAIN UI ---
st.title("🛡️ Algo Command Center")
tab1, tab2, tab3, tab4 = st.tabs(["📊 Performance", "⚙️ Strategies", "🕹️ Manual Control", "🔍 Debug Console"])

with tab1:
    st.subheader("Holdings & Assets")
    positions = broker.list_positions()
    if isinstance(positions, dict) and "ERROR" in positions:
        st.error(f"Failed to fetch assets: {positions['ERROR']}")
    elif positions:
        pos_df = pd.DataFrame([{"Symbol": p.symbol, "Qty": p.qty, "Price": p.current_price} for p in positions])
        st.table(pos_df)
    else:
        st.info("No active positions.")

with tab2:
    st.subheader("Active Logic Settings")
    with sqlite3.connect(DB_PATH) as conn:
        df_strat = pd.read_sql("SELECT * FROM strategies", conn)
        if df_strat.empty:
            st.info("No strategies found. Run analyzer.py inside the container.")
            if st.button("🏃 Run Analyzer Now"):
                os.system("python src/analyzer.py &")
                st.success("Analyzer started in background...")
        else:
            st.dataframe(df_strat, use_container_width=True)

with tab3:
    st.subheader("Manual Override")
    # ... (Manual order code stays the same) ...

with tab4:
    st.subheader("🔍 System Logs & Debugging")
    st.write("### Environment Variables Check")
    st.write(f"**API URL:** `{os.getenv('PAPER_URL')}`")
    st.write(f"**API Key Present:** `{'✅ Yes' if os.getenv('APIKEY') else '❌ No'}`")
    
    st.write("### Raw API Connection Test")
    if is_connected:
        st.success(conn_msg)
    else:
        st.code(conn_msg, language="bash")
        
    st.write("### Database Path")
    st.code(DB_PATH)

with tab4: # The Debug Console we created earlier
    st.subheader("📜 Live Engine Logs")
    if st.button("🔄 Refresh Logs"):
        # This reads the last 20 lines of the container logs
        # Note: This only works if Streamlit has permission to run shell commands
        try:
            logs = os.popen("docker logs algo_heart --tail 20").read()
            st.code(logs, language="text")
        except:
            st.error("Cannot access Docker logs from UI. Check permissions.")