import streamlit as st
import pandas as pd
import sqlite3
import os, socket, platform, json, time, psutil
from datetime import datetime, timezone
from src.broker import Broker
from src.config import Config
from src.database import get_status, update_status, delete_strategy, DB_PATH

st.set_page_config(page_title="Algo Command Center", layout="wide")

# --- COMPRESSED CSS ---
st.markdown("""
<style>
    [data-testid="stVerticalBlock"] { gap: 0.2rem !important; }
    .stMainBlockContainer { padding-top: 1rem !important; padding-bottom: 1rem !important; }
    .stMetric { padding: 0.1rem !important; }
    [data-testid="stMetricValue"] { font-size: 1.4rem !important; }
    .debug-card { background: #f0f2f6; padding: 6px; border-radius: 4px; font-family: monospace; font-size: 11px; margin-bottom: 5px;}
</style>
""", unsafe_allow_html=True)

broker = Broker()
conn_ok, conn_msg = broker.test_connection()

# --- SIDEBAR: Portfolio & Stats ---
with st.sidebar:
    st.markdown(f"**MODE: {Config.MODE}**")
    if conn_ok:
        st.success("🟢 API ONLINE")
        acc = broker.get_account_stats()
        st.metric("Equity", f"${acc.get('Equity', 0):,.0f}")
        st.metric("Power", f"${acc.get('Power', 0):,.0f}")
        
        # Portfolio Graph
        st.markdown("---")
        st.caption("24H Equity Curve")
        try:
            from alpaca.trading.requests import GetPortfolioHistoryRequest
            hist = broker.client.get_portfolio_history(GetPortfolioHistoryRequest(period="1D", timeframe="15Min"))
            if hist and hist.equity:
                st.area_chart(pd.DataFrame({"Equity": hist.equity}), height=100, color="#29b5e8")
        except: st.caption("Graph unavailable")
        
        # Historic Stats
        st.markdown("---")
        perf = broker.get_portfolio_history_stats()
        c1, c2 = st.columns(2)
        c1.write(f"1D: {perf.get('1D','N/A')}"); c2.write(f"1W: {perf.get('1W','N/A')}")
        c3, c4 = st.columns(2)
        c3.write(f"1M: {perf.get('1M','N/A')}"); c4.write(f"1Y: {perf.get('1A','N/A')}")
    else:
        st.error("🔴 DISCONNECTED")

    st.divider()
    eng = get_status("engine_running") == "1"
    if st.button("🛑 STOP" if eng else "🚀 START", use_container_width=True):
        update_status("engine_running", "0" if eng else "1"); st.rerun()

# Market Bar
if broker: st.info(f"**{broker.get_market_clock()}**")

# --- TABS ---
t1, t2, t3, t4, t5 = st.tabs(["📊 Assets", "⚙️ Strategies", "🕹️ Manual", "📉 Execution", "🔍 Debug"])

with t1: # ASSETS
    positions = broker.get_all_positions()
    if positions:
        for p in positions:
            with st.expander(f"{p.symbol} | {float(p.qty):.1f} sh | P/L: ${float(p.unrealized_pl):.2f}"):
                c1, c2, c3 = st.columns(3)
                c1.metric("Price", f"${float(p.current_price):.2f}")
                c2.metric("P/L %", f"{float(p.unrealized_plpc or 0)*100:+.2f}%")
                c3.metric("Value", f"${float(p.market_value):,.2f}")
    else: st.info("No active positions.")

with t3: # FULL MANUAL TICKET
    st.subheader("🕹️ Advanced Manual Ticket")
    with st.form("manual_trade"):
        c1, c2, c3, c4 = st.columns(4)
        msym = c1.text_input("Symbol", "TSLA").upper()
        mqty = c2.number_input("Qty", 1.0)
        mside = c3.selectbox("Side", ["buy", "sell"])
        mtype = c4.selectbox("Type", ["market", "limit", "stop", "trailing_stop"])
        
        p1, p2, p3 = st.columns(3)
        lpx = p1.number_input("Limit $", 0.0); spx = p2.number_input("Stop $", 0.0); tif = p3.selectbox("TIF", ["gtc", "day"])
        
        st.caption("Bracket Guardrails")
        b1, b2 = st.columns(2)
        tp = b1.number_input("Take Profit $", 0.0); sl = b2.number_input("Stop Loss $", 0.0)
        
        if st.form_submit_button("🚀 Submit Order", use_container_width=True):
            ok, res = broker.submit_order_v2(mtype, symbol=msym, qty=mqty, side=mside, limit_price=lpx if lpx>0 else None, time_in_force=tif)
            if ok: st.success(f"Sent: {res}")
            else: st.error(res)

with t4: # PERSISTENT EXECUTION
    st.subheader("⚡ Persistent History")
    with sqlite3.connect(DB_PATH) as conn:
        try:
            df = pd.read_sql("SELECT * FROM trade_execution ORDER BY submitted_at DESC", conn)
            st.dataframe(df, use_container_width=True, height=450)
        except: st.info("No records found.")

with t5: # Diagnostics Tab
    st.header("🔍 System Diagnostics")
    
    # 1. Physical Resource Gauges
    r1, r2, r3 = st.columns(3)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    # RAM
    r1.metric("RAM Usage", f"{mem.percent}%", f"{mem.used//1024**2}MB Used")
    
    # DISK (The "Nuke" Indicator)
    disk_color = "normal" if disk.percent < 85 else "inverse"
    r2.metric("Disk Space", f"{disk.free//1024**3}GB Free", f"{disk.percent}% Used", delta_color=disk_color)
    
    # LATENCY
    avg_lat = broker.get_mean_latency_24h()
    r3.metric("Avg Latency (24h)", f"{avg_lat:.1f}ms")

    st.divider()
    
    # 2. Key Check & Endpoint Status
    st.subheader("2. API Routing Logic")
    act_key, _, is_paper = Config.get_auth()
    st.markdown(f"""<div class="debug-card">
        <b>Active Mode:</b> {Config.MODE}<br>
        <b>In-Use Key:</b> {act_key[:4]}...{act_key[-4:]}<br>
        <b>Target Endpoint:</b> {"Paper Simulator" if is_paper else "Live Exchange"}
    </div>""", unsafe_allow_html=True)