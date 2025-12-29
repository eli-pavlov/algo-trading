import streamlit as st
import pandas as pd
import sqlite3
import time
import json
import os
import socket
import platform
from datetime import datetime, timezone
from src.broker import Broker
from src.config import Config
from src.database import get_status, update_status, delete_strategy, DB_PATH

# ---------------------------------------------------------
# Page Config & Compressed UI Styling
# ---------------------------------------------------------
st.set_page_config(page_title="Algo Command Center", layout="wide", page_icon="🛡️")

st.markdown(f"""
<style>
    /* Remove vertical gaps between elements */
    [data-testid="stVerticalBlock"] {{ gap: 0.3rem !important; }}
    /* Tighten container padding */
    .stMainBlockContainer {{ padding-top: 1rem !important; padding-bottom: 1rem !important; }}
    /* Metrics Font Size */
    [data-testid="stMetricValue"] {{ font-size: 1.5rem !important; }}
    /* Mode Badges */
    .env-badge {{
        background-color: {'#fffbeb' if Config.MODE == 'PAPER' else '#fef2f2'};
        color: {'#b7791f' if Config.MODE == 'PAPER' else '#c53030'};
        padding: 6px; border: 1px dashed {'#ecc94b' if Config.MODE == 'PAPER' else '#fc8181'};
        text-align: center; font-weight: bold; border-radius: 5px; margin-bottom: 10px;
    }}
    .debug-card {{ background: #f0f2f6; padding: 5px; border-radius: 4px; font-family: monospace; font-size: 12px; }}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# Sidebar: Metrics & Portfolio Graph
# ---------------------------------------------------------
broker = Broker()
conn_ok, conn_msg = broker.test_connection()

with st.sidebar:
    st.markdown(f'<div class="env-badge">{"⚠️" if Config.MODE == "PAPER" else "🚨"} {Config.MODE} TRADING</div>', unsafe_allow_html=True)
    st.title("📡 Overview")
    st.markdown(f"**MODE:** `{Config.MODE}`")
    
    if conn_ok:
        st.success("🟢 API ONLINE")
        acc = broker.get_account_stats()
        st.metric("Buying Power", f"${acc.get('Power', 0):,.0f}")
        st.metric("Equity", f"${acc.get('Equity', 0):,.0f}")
        
        # --- Nice Portfolio Graph ---
        st.markdown("---")
        st.caption("24H Equity Curve")
        try:
            # We fetch 1D history to show the trend on the left
            from alpaca.trading.requests import GetPortfolioHistoryRequest
            hist_req = GetPortfolioHistoryRequest(period="1D", timeframe="15Min")
            hist = broker.client.get_portfolio_history(hist_req)
            if hist and hist.equity:
                chart_df = pd.DataFrame({"Equity": hist.equity})
                st.area_chart(chart_df, height=120, color="#29b5e8")
        except:
            st.caption("Graph currently unavailable")
    else:
        st.error("🔴 DISCONNECTED")
        st.caption(conn_msg)
    
    st.divider()
    eng = get_status("engine_running") == "1"
    if st.button("🛑 STOP" if eng else "🚀 START", use_container_width=True):
        update_status("engine_running", "0" if eng else "1")
        st.rerun()

# Market Bar
if broker: st.info(f"**{broker.get_market_clock()}**")

# ---------------------------------------------------------
# Main Tabs
# ---------------------------------------------------------
t1, t2, t3, t4, t5 = st.tabs(["📊 Assets", "⚙️ Strategies", "🕹️ Manual", "📉 Execution", "🔍 Debug"])

with t1: # ASSETS
    if broker and conn_ok:
        try:
            positions = broker.get_all_positions()
            if positions:
                for p in positions:
                    pl = float(p.unrealized_pl or 0.0)
                    pl_pct = float(p.unrealized_plpc or 0.0) * 100
                    with st.expander(f"**{p.symbol}** | {float(p.qty):.1f} sh | P/L: ${pl:+.2f} ({pl_pct:+.2f}%)"):
                        c1, c2, c3 = st.columns(3)
                        c1.metric("Price", f"${float(p.current_price):.2f}")
                        c2.metric("P/L %", f"{pl_pct:+.2f}%")
                        c3.metric("Market Value", f"${float(p.market_value):,.2f}")
            else: st.info("No active positions.")
        except Exception as e: st.error(f"Render Error: {e}")

with t2: # STRATEGIES
    with sqlite3.connect(DB_PATH) as conn:
        try:
            df_strat = pd.read_sql("SELECT * FROM strategies", conn)
            if not df_strat.empty:
                for _, row in df_strat.iterrows():
                    params = json.loads(row['params'])
                    c1, c2, c3 = st.columns([2, 4, 1])
                    c1.write(f"**{row['symbol']}**")
                    c2.caption(f"TP: +{params.get('target', 0)*100:.1f}% | SL: -{params.get('stop', 0)*100:.1f}%")
                    if c3.button("🗑️", key=f"del_{row['symbol']}"):
                        delete_strategy(row['symbol']); st.rerun()
                    st.divider()
            else: st.info("No active strategies.")
        except: st.error("Database locked or missing.")

with t3: # MANUAL
    with st.form("manual_trade"):
        st.caption("Standard Market/Limit Order")
        c1, c2, c3 = st.columns(3)
        msym = c1.text_input("Symbol", "AAPL").upper()
        mqty = c2.number_input("Qty", 1.0)
        mside = c3.selectbox("Side", ["buy", "sell"])
        if st.form_submit_button("🚀 Execute Order"):
            ok, msg = broker.submit_order(msym, mqty, mside, "market")
            if ok: st.success(msg)
            else: st.error(msg)

with t4: # PERSISTENT EXECUTION
    st.subheader("⚡ Full Trade History")
    with sqlite3.connect(DB_PATH) as conn:
        try:
            df_hist = pd.read_sql("SELECT * FROM trade_execution ORDER BY submitted_at DESC", conn)
            st.dataframe(df_hist, use_container_width=True, height=500)
        except: st.info("No trades found in DB.")

with t5: # DEBUG
    st.subheader("🔍 Diagnostics")
    c1, c2 = st.columns(2)
    with c1:
        st.write("**API Verification (Masked)**")
        def verify(name):
            val = os.getenv(name)
            return f"<span style='color:green'>✅ {val[:4]}...</span>" if val else "<span style='color:red'>❌ Missing</span>"
        
        st.markdown(f"""<div class="debug-card">
            MODE: {Config.MODE}<br>
            LIVE: {verify('APIKEY_LIVE')}<br>
            PAPER: {verify('APIKEY_PAPER')}<br>
            MAIN: {verify('APIKEY')}
        </div>""", unsafe_allow_html=True)
    with c2:
        st.write("**System Status**")
        st.markdown(f"""<div class="debug-card">
            Host: {socket.gethostname()}<br>
            OS: {platform.system()}<br>
            DB: {os.path.getsize(DB_PATH)/1024:.1f} KB
        </div>""", unsafe_allow_html=True)