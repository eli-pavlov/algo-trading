import streamlit as st
import pandas as pd
import sqlite3
import time
import json
import os
import socket
import platform
from src.broker import Broker
from src.config import Config
from src.database import get_status, update_status, delete_strategy, DB_PATH

st.set_page_config(page_title="Algo Command Center", layout="wide", page_icon="🛡️")

# Custom UI Styling
st.markdown(f"""
<style>
    .env-badge {{
        background-color: {'#fffbeb' if Config.MODE == 'PAPER' else '#fef2f2'};
        color: {'#b7791f' if Config.MODE == 'PAPER' else '#c53030'};
        padding: 10px; border: 2px dashed {'#ecc94b' if Config.MODE == 'PAPER' else '#fc8181'};
        text-align: center; font-weight: bold; margin-bottom: 20px; border-radius: 8px;
    }}
</style>
""", unsafe_allow_html=True)

broker = Broker()
conn_ok, conn_msg = broker.test_connection()

# Sidebar
with st.sidebar:
    st.markdown(f'<div class="env-badge">{"⚠️" if Config.MODE == "PAPER" else "🚨"} {Config.MODE} TRADING</div>', unsafe_allow_html=True)
    st.title("📡 Overview")
    if conn_ok: st.success("🟢 API ONLINE")
    else: st.error("🔴 DISCONNECTED"); st.caption(conn_msg)
    
    if broker and conn_ok:
        acc = broker.get_account_stats()
        st.metric("Buying Power", f"${acc.get('Power', 0):,.2f}")
        st.metric("Cash", f"${acc.get('Cash', 0):,.2f}")
        st.metric("Equity", f"${acc.get('Equity', 0):,.2f}")
        
        st.markdown("---")
        hist = broker.get_portfolio_history_stats()
        c1, c2 = st.columns(2)
        c1.caption("1D"); c1.write(hist.get('1D'))
        c2.caption("1W"); c2.write(hist.get('1W'))
        c3, c4 = st.columns(2)
        c3.caption("1M"); c3.write(hist.get('1M'))
        c4.caption("1Y"); c4.write(hist.get('1A'))

    st.markdown("---")
    eng = get_status("engine_running") == "1"
    if st.button("🛑 STOP ENGINE" if eng else "🚀 START ENGINE", use_container_width=True):
        update_status("engine_running", "0" if eng else "1"); st.rerun()

# Market Bar
if broker: st.info(f"**{broker.get_market_clock()}**")

t1, t2, t3, t4, t5 = st.tabs(["📊 Assets", "⚙️ Strategies", "🕹️ Manual", "📉 Execution", "🔍 Debug"])

with t1: # Assets
    if broker and conn_ok:
        positions = broker.get_all_positions()
        if positions:
            for p in positions:
                pl_pct = float(p.unrealized_plpc) * 100
                with st.expander(f"{p.symbol} | {float(p.qty)} sh | P/L: ${float(p.unrealized_pl):.2f} ({pl_pct:+.2f}%)"):
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Price", f"${float(p.current_price):.2f}")
                    c2.metric("Market Value", f"${float(p.market_value):,.2f}")
                    c3.metric("P/L %", f"{pl_pct:+.2f}%")
        else: st.info("No active positions.")

with t2: # Strategies
    with sqlite3.connect(DB_PATH) as conn:
        try:
            df = pd.read_sql("SELECT * FROM strategies", conn)
            for i, r in df.iterrows():
                p = json.loads(r['params'])
                with st.container():
                    c1, c2, c3, c4 = st.columns([2, 2, 2, 1])
                    c1.write(f"**{r['symbol']}**")
                    c2.caption(f"Target: +{p.get('target',0)*100:.1f}%")
                    c3.caption(f"Stop: -{p.get('stop',0)*100:.1f}%")
                    if c4.button("🗑️", key=f"del_{r['symbol']}"):
                        delete_strategy(r['symbol']); st.rerun()
                st.divider()
        except: st.info("No strategies loaded.")

with t3: # Manual
    with st.form("manual_trade"):
        c1, c2, c3 = st.columns(3)
        sym = c1.text_input("Symbol", "AAPL").upper()
        qty = c2.number_input("Qty", 1.0)
        side = c3.selectbox("Side", ["buy", "sell"])
        if st.form_submit_button("🚀 Execute Market Order"):
            ok, msg = broker.submit_order(sym, qty, side, "market")
            if ok: st.success(msg)
            else: st.error(msg)

with t4: # Execution
    st.subheader("Last 50 Executions")
    with sqlite3.connect(DB_PATH) as conn:
        try:
            df = pd.read_sql("SELECT * FROM trade_execution ORDER BY submitted_at DESC LIMIT 50", conn)
            st.dataframe(df, use_container_width=True)
        except: st.info("No logs yet.")

with t5: # Debug
    st.header("🔍 System Diagnostics")
    c1, c2, c3 = st.columns(3)
    c1.metric("Hostname", socket.gethostname())
    c2.metric("Python", platform.python_version())
    
    hb_path = "/tmp/heartbeat"
    if os.path.exists(hb_path):
        diff = time.time() - os.path.getmtime(hb_path)
        c3.metric("Heartbeat", "✅ Active" if diff < 65 else "⚠️ Stalled", delta=f"{int(diff)}s ago")
    
    st.divider()
    st.subheader("API Keys Verification")
    def mask(k):
        val = os.getenv(k, "")
        return f"✅ {val[:4]}...{val[-4:]}" if val else "❌ Missing"
    
    st.code(f"MODE: {Config.MODE}\nLIVE: {mask('APIKEY_LIVE')}\nPAPER: {mask('APIKEY_PAPER')}")
    
    st.divider()
    st.subheader("Raw Database Explorer")
    with sqlite3.connect(DB_PATH) as conn:
        tables = pd.read_sql("SELECT name FROM sqlite_master WHERE type='table'", conn)
        selected = st.selectbox("Inspect Table", tables['name'].tolist())
        if selected:
            st.dataframe(pd.read_sql(f"SELECT * FROM {selected} LIMIT 20", conn), use_container_width=True)