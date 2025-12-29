import streamlit as st
import pandas as pd
import sqlite3
import os
import socket
import platform
from src.broker import Broker
from src.config import Config
from src.database import get_status, update_status, delete_strategy, DB_PATH

st.set_page_config(page_title="Algo Command Center", layout="wide", page_icon="🛡️")

# --- TIGHT UI CSS ---
st.markdown("""
<style>
    [data-testid="stVerticalBlock"] { gap: 0.3rem !important; }
    .stMetric { padding: 0.2rem !important; }
    .stMainBlockContainer { padding-top: 1rem !important; }
    .debug-card { 
        background-color: #f8f9fa; 
        padding: 8px; 
        border-radius: 5px; 
        border-left: 5px solid #4a5568;
        font-family: monospace;
        font-size: 13px;
    }
</style>
""", unsafe_allow_html=True)

broker = Broker()
conn_ok, conn_msg = broker.test_connection()

with st.sidebar:
    st.title("📡 Overview")
    st.markdown(f"**MODE:** `{Config.MODE}`")
    if conn_ok: st.success("🟢 API ONLINE")
    else: st.error("🔴 DISCONNECTED")
    
    acc = broker.get_account_stats()
    st.metric("Buying Power", f"${acc.get('Power', 0):,.0f}")
    st.metric("Equity", f"${acc.get('Equity', 0):,.0f}")
    
    st.divider()
    eng = get_status("engine_running") == "1"
    if st.button("🛑 STOP" if eng else "🚀 START", use_container_width=True):
        update_status("engine_running", "0" if eng else "1"); st.rerun()

t1, t2, t3, t4, t5 = st.tabs(["📊 Assets", "⚙️ Strategies", "🕹️ Manual", "📉 Execution", "🔍 Debug"])

# --- PERSISTENT EXECUTION TAB ---
with t4:
    st.subheader("⚡ Persistent Trade History")
    with sqlite3.connect(DB_PATH) as conn:
        try:
            # Query all trades from DB, no limit
            df_exec = pd.read_sql("SELECT * FROM trade_execution ORDER BY submitted_at DESC", conn)
            if not df_exec.empty:
                st.dataframe(df_exec, use_container_width=True, height=500) # Scrollable height
            else:
                st.info("No trades recorded in database yet.")
        except: st.error("Could not load execution logs.")

# --- TIGHT DEBUG TAB ---
with t5:
    st.subheader("🔍 Diagnostics")
    c1, c2 = st.columns(2)
    
    with c1:
        st.write("**Credentials Verification**")
        def verify(key_name):
            val = os.getenv(key_name)
            if not val: return "<span style='color:red'>❌ Missing</span>"
            return f"<span style='color:green'>✅ {val[:4]}...{val[-4:]}</span>"

        st.markdown(f"""<div class="debug-card">
            MODE:  {Config.MODE}<br>
            LIVE:  {verify('APIKEY_LIVE')}<br>
            PAPER: {verify('APIKEY_PAPER')}<br>
            MAIN:  {verify('APIKEY')}
        </div>""", unsafe_allow_html=True)

    with c2:
        st.write("**System Status**")
        st.markdown(f"""<div class="debug-card">
            HOST: {socket.gethostname()}<br>
            OS:   {platform.system()} {platform.release()}<br>
            DB:   {os.path.getsize(DB_PATH)/1024:.1f} KB
        </div>""", unsafe_allow_html=True)
    
    if st.button("Network Latency Test", use_container_width=True):
        import time
        start = time.time()
        broker.client.get_clock()
        st.write(f"Ping: {int((time.time()-start)*1000)}ms")