import streamlit as st
import pandas as pd
import sqlite3
import time
import json
import socket
import platform
import os
import requests
from datetime import datetime
from src.broker import Broker
from src.config import Config
from src.database import get_status, update_status, delete_strategy, DB_PATH

# ---------------------------------------------------------
# Streamlit Page Config
# ---------------------------------------------------------
st.set_page_config(page_title="Algo Command Center", layout="wide", page_icon="🛡️")

# ---------------------------------------------------------
# Custom CSS (Badges, Buttons, Tables)
# ---------------------------------------------------------
st.markdown(f"""
<style>
    div.stButton > button {{
        box-shadow: 0px 4px 0px #4a5568;
        transition: all 0.1s;
        border: 1px solid #cbd5e0;
        border-radius: 8px;
        font-weight: 600;
    }}
    div.stButton > button:active {{ transform: translateY(4px); box-shadow: none; }}
    
    .env-badge {{
        background-color: {'#fffbeb' if Config.MODE == 'PAPER' else '#fef2f2'};
        color: {'#b7791f' if Config.MODE == 'PAPER' else '#c53030'};
        padding: 8px;
        border: 2px dashed {'#ecc94b' if Config.MODE == 'PAPER' else '#fc8181'};
        text-align: center;
        font-weight: bold;
        margin-bottom: 15px;
        border-radius: 5px;
    }}
    
    .strategy-row {{ padding: 8px 0; border-bottom: 1px solid #eee; }}
    .debug-box {{ background-color: #f0f2f6; padding: 10px; border-radius: 5px; font-family: monospace; font-size: 0.85em; }}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# Initialize Broker & Connection Check
# ---------------------------------------------------------
# Initialize without arguments -> defaults to Config.MODE
try:
    broker = Broker()
    conn_ok, conn_msg = broker.test_connection()
except Exception as e:
    broker = None
    conn_ok = False
    conn_msg = str(e)

# ---------------------------------------------------------
# Sidebar: Controls & Overview
# ---------------------------------------------------------
with st.sidebar:
    # Environment Badge
    env_icon = "⚠️" if Config.MODE == "PAPER" else "🚨"
    st.markdown(f'<div class="env-badge">{env_icon} {Config.MODE} TRADING</div>', unsafe_allow_html=True)
    
    st.title("📡 Overview")
    if conn_ok:
        st.success("🟢 API ONLINE")
    else:
        st.error("🔴 DISCONNECTED")
        st.caption(conn_msg)
        
    st.markdown("---")
    
    # Account Stats
    if broker and conn_ok:
        acc = broker.get_account_stats()
        st.metric("Buying Power", f"${acc.get('Power', 0):,.2f}")
        st.metric("Cash", f"${acc.get('Cash', 0):,.2f}")
        st.metric("Equity", f"${acc.get('Equity', 0):,.2f}")
    else:
        st.metric("Buying Power", "$0.00")
        st.metric("Cash", "$0.00")
    
    st.markdown("---")
    
    # Engine Control
    eng = get_status("engine_running") == "1"
    btn_label = "🛑 STOP ENGINE" if eng else "🚀 START ENGINE"
    if st.button(btn_label, use_container_width=True):
        update_status("engine_running", "0" if eng else "1")
        st.rerun()

# ---------------------------------------------------------
# Market Clock Status
# ---------------------------------------------------------
if broker:
    clock_msg = broker.get_market_clock()
    if "🟢" in clock_msg:
        st.info(f"**{clock_msg}**")
    else:
        st.warning(f"**{clock_msg}**")

# ---------------------------------------------------------
# Main Tabs
# ---------------------------------------------------------
t1, t2, t3, t4, t5 = st.tabs(["📊 Assets", "⚙️ Strategies", "🕹️ Manual", "📉 Execution", "🔍 Debug"])

# --- TAB 1: ASSETS (Positions) ---
with t1:
    if broker and conn_ok:
        try:
            positions = broker.get_all_positions()
            if positions:
                for p in positions:
                    # alpaca-py objects use dot notation
                    sym = p.symbol
                    qty = float(p.qty)
                    pl = float(p.unrealized_pl)
                    price = float(p.current_price)
                    entry = float(p.avg_entry_price)
                    pl_pct = float(p.unrealized_plpc) * 100
                    
                    with st.expander(f"{sym} | {qty} sh | P/L: ${pl:.2f} ({pl_pct:+.2f}%)"):
                        c1, c2, c3, c4 = st.columns(4)
                        c1.metric("Current Price", f"${price:.2f}")
                        c2.metric("Avg Entry", f"${entry:.2f}")
                        c3.metric("Market Value", f"${float(p.market_value):,.2f}")
                        c4.metric("Total P/L", f"${pl:.2f}", delta=f"{pl_pct:.2f}%")
            else:
                st.info("No active positions.")
        except Exception as e:
            st.error(f"Error fetching positions: {e}")
    else:
        st.warning("Broker disconnected.")

# --- TAB 2: STRATEGIES ---
with t2:
    if os.path.exists(DB_PATH):
        with sqlite3.connect(DB_PATH) as conn:
            df = pd.read_sql("SELECT * FROM strategies", conn)
            if not df.empty:
                # Header
                c = st.columns([1.5, 1, 1, 1, 1, 0.5])
                c[0].markdown("**Symbol**")
                c[1].markdown("RSI <")
                c[2].markdown("ADX >")
                c[3].markdown("TP")
                c[4].markdown("SL")
                st.divider()
                
                # Rows
                for i, r in df.iterrows():
                    try:
                        p = json.loads(r['params'])
                        c = st.columns([1.5, 1, 1, 1, 1, 0.5])
                        c[0].markdown(f"**{r['symbol']}**")
                        c[1].caption(f"{p.get('rsi_trend')}")
                        c[2].caption(f"{p.get('adx_trend')}")
                        c[3].markdown(f"<span style='color:green'>+{p.get('target', 0)*100:.1f}%</span>", unsafe_allow_html=True)
                        c[4].markdown(f"<span style='color:red'>-{p.get('stop', 0)*100:.1f}%</span>", unsafe_allow_html=True)
                        
                        if c[5].button("🗑️", key=f"d_{r['symbol']}"):
                            delete_strategy(r['symbol'])
                            st.rerun()
                        st.markdown("<div class='strategy-row'></div>", unsafe_allow_html=True)
                    except Exception:
                        pass
            else:
                st.info("No active strategies found. Run the Tuner to generate strategies.")
    else:
        st.error("Database not initialized.")

# --- TAB 3: MANUAL TRADE ---
with t3:
    st.subheader("🕹️ Manual Trade Ticket")
    st.caption("Orders placed here use the Bracket logic (Auto TP/SL) if available.")
    
    with st.form("manual"):
        c1, c2, c3, c4 = st.columns(4)
        sym = c1.text_input("Symbol", "TSLA").upper()
        qty = c2.number_input("Quantity", 1.0, step=0.1)
        side = c3.selectbox("Side", ["buy", "sell"])
        type = c4.selectbox("Type", ["market", "limit"])

        c5, c6 = st.columns(2)
        lp = c5.number_input("Limit Price (Optional)", 0.0)
        
        st.markdown("**Bracket Settings (Buy Orders Only)**")
        b1, b2 = st.columns(2)
        tp_price = b1.number_input("Take Profit Price", 0.0)
        sl_price = b2.number_input("Stop Loss Price", 0.0)

        if st.form_submit_button("🚀 Submit Order"):
            if broker:
                if side == "buy" and tp_price > 0 and sl_price > 0:
                    # Use Bracket
                    ok = broker.buy_bracket(sym, qty, tp_price, sl_price)
                    msg = "Bracket Order Sent" if ok else "Bracket Failed"
                else:
                    # Standard Order
                    limit = lp if lp > 0 else None
                    ok, msg = broker.submit_order(sym, qty, side, type, limit_px=limit)
                
                if ok:
                    st.success(f"✅ {msg}")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error(f"❌ {msg}")
            else:
                st.error("Broker not connected.")

# --- TAB 4: EXECUTION (TCA) ---
with t4:
    st.subheader("⚡ Trade Execution Logs")
    c1, c2 = st.columns([1, 4])
    auto_refresh = c1.checkbox("🔴 Live Monitor", True)
    c2.caption("Shows API latency, fill speeds, and slippage.")
    
    placeholder = st.empty()
    
    while True:
        # Trigger a sync attempt
        if broker:
            try: broker.sync_tca_logs()
            except: pass
        
        with sqlite3.connect(DB_PATH) as conn:
            try:
                df = pd.read_sql("SELECT * FROM trade_execution ORDER BY submitted_at DESC LIMIT 50", conn)
            except:
                df = pd.DataFrame()
        
        with placeholder.container():
            if not df.empty:
                # Metrics
                avg_api = df.head(10)['api_latency_ms'].mean()
                avg_fill = df.head(10)['fill_latency_ms'].mean()
                
                m1, m2 = st.columns(2)
                m1.metric("Avg API Latency", f"{avg_api:.0f} ms")
                m2.metric("Avg Fill Speed", f"{avg_fill:.0f} ms")
                
                # Table
                disp = df[['submitted_at', 'symbol', 'side', 'order_type', 'api_latency_ms', 'fill_latency_ms', 'status']].copy()
                st.dataframe(disp, use_container_width=True)
            else:
                st.info("No trade history available yet.")
        
        if not auto_refresh:
            break
        time.sleep(2)

# --- TAB 5: DEBUG ---
with t5:
    st.header("🔍 System Diagnostics")
    
    # 1. System Health
    st.subheader("1. System Health")
    c1, c2, c3 = st.columns(3)
    c1.metric("Hostname", socket.gethostname())
    c2.metric("Python", platform.python_version())
    
    # Heartbeat Check
    hb_path = "/tmp/heartbeat"
    if os.path.exists(hb_path):
        last_beat = os.path.getmtime(hb_path)
        diff = time.time() - last_beat
        status = "✅ Alive" if diff < 60 else f"⚠️ Stalled ({int(diff)}s)"
        c3.metric("Heartbeat", status, delta=f"{int(diff)}s ago", delta_color="inverse")
    else:
        c3.metric("Heartbeat", "❌ Missing")

    st.divider()

    # 2. Config & Secrets (Masked)
    st.subheader("2. Active Configuration")
    
    def mask(val):
        if not val: return "❌ Not Set"
        if len(val) < 8: return "******"
        return f"{val[:4]}...{val[-4:]}"

    k_live, s_live, _ = Config.get_auth("LIVE")
    k_paper, s_paper, _ = Config.get_auth("PAPER")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Live Credentials**")
        st.code(f"API Key: {mask(k_live)}\nSecret:  {mask(s_live)}\nURL:     {Config.LIVE_URL}")
    with c2:
        st.markdown("**Paper Credentials**")
        st.code(f"API Key: {mask(k_paper)}\nSecret:  {mask(s_paper)}\nURL:     {Config.PAPER_URL}")

    st.info(f"**Current Trading Mode:** `{Config.MODE}`")

    st.divider()

    # 3. Database Inspection
    st.subheader("3. Database Inspector")
    if os.path.exists(DB_PATH):
        size_kb = os.path.getsize(DB_PATH) / 1024
        st.caption(f"DB Location: {DB_PATH} ({size_kb:.1f} KB)")
        
        with sqlite3.connect(DB_PATH) as conn:
            tables = pd.read_sql("SELECT name FROM sqlite_master WHERE type='table'", conn)
            if not tables.empty:
                selected_table = st.selectbox("View Table:", tables['name'].tolist())
                if selected_table:
                    raw_df = pd.read_sql(f"SELECT * FROM {selected_table} ORDER BY rowid DESC LIMIT 50", conn)
                    st.dataframe(raw_df, use_container_width=True)
            else:
                st.warning("Database is empty (no tables).")
    else:
        st.error("Database file missing.")

    st.divider()

    # 4. Network Test
    st.subheader("4. Network Latency Test")
    if st.button("Ping Alpaca API"):
        if broker:
            try:
                start = time.time()
                broker.client.get_clock()
                latency = (time.time() - start) * 1000
                st.success(f"✅ Pong! Latency: {latency:.0f} ms")
            except Exception as e:
                st.error(f"❌ Ping Failed: {e}")
        else:
            st.error("Broker not initialized.")