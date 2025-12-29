import streamlit as st
import pandas as pd
import sqlite3
import time
import json
import os
import socket
import platform
import requests
from datetime import datetime
from src.broker import Broker
from src.database import get_status, update_status, delete_strategy, DB_PATH

st.set_page_config(page_title="Algo Command Center", layout="wide", page_icon="🛡️")

st.markdown("""
<style>
    div.stButton > button { box-shadow: 0px 4px 0px #4a5568; transition: all 0.1s; border: 1px solid #cbd5e0; border-radius: 8px; font-weight: 600; }
    div.stButton > button:active { transform: translateY(4px); box-shadow: none; }
    .paper-badge { background-color: #fffbeb; color: #b7791f; padding: 8px; border: 2px dashed #ecc94b; text-align: center; font-weight: bold; margin-bottom: 15px; }
    .strategy-row { padding: 8px 0; border-bottom: 1px solid #eee; }
    .debug-box { background-color: #f0f2f6; padding: 10px; border-radius: 5px; font-family: monospace; font-size: 0.85em; }
</style>
""", unsafe_allow_html=True)

broker = Broker()
conn_status, conn_msg = broker.test_connection()

with st.sidebar:
    st.markdown('<div class="paper-badge">⚠️ Alpaca Paper Trading</div>', unsafe_allow_html=True)
    st.title("📡 Overview")
    if conn_status: st.success("🟢 API ONLINE")
    else: st.error("🔴 DISCONNECTED")
    st.markdown("---")
    acc = broker.get_account_stats()
    st.metric("Buying Power", f"${acc.get('Power', 0):,.2f}")
    st.metric("Cash", f"${acc.get('Cash', 0):,.2f}")
    st.markdown("---")
    hist = broker.get_portfolio_history_stats()
    c1,c2 = st.columns(2); c1.caption("1D"); c1.write(hist.get('1D')); c2.caption("1W"); c2.write(hist.get('1W'))
    c3,c4 = st.columns(2); c3.caption("1M"); c3.write(hist.get('1M')); c4.caption("1Y"); c4.write(hist.get('1A'))
    st.markdown("---")
    eng = get_status("engine_running") == "1"
    if st.button("🛑 STOP" if eng else "🚀 START", use_container_width=True):
        update_status("engine_running", "0" if eng else "1"); st.rerun()

clock = broker.get_market_clock()
if "🟢" in clock: st.info(f"**{clock}**")
else: st.warning(f"**{clock}**")

t1, t2, t3, t4, t5 = st.tabs(["📊 Assets", "⚙️ Strategies", "🕹️ Manual", "📉 Execution (TCA)", "🔍 Debug"])

with t1:
    try:
        pos = broker.api.list_positions()
        if pos:
            for p in pos:
                with st.expander(f"{p.symbol} | {p.qty} sh | P/L: ${float(p.unrealized_pl):.2f}"):
                    c1,c2,c3,c4=st.columns(4)
                    c1.metric("Price", f"${float(p.current_price):.2f}")
                    c2.metric("Entry", f"${float(p.avg_entry_price):.2f}")
                    c3.metric("Day P/L", f"${float(p.unrealized_intraday_pl):.2f}")
                    c4.metric("Total", f"${float(p.unrealized_pl):.2f}")
        else: st.info("No active positions.")
    except Exception as e: st.error(str(e))

with t2:
    with sqlite3.connect(DB_PATH) as conn:
        df = pd.read_sql("SELECT * FROM strategies", conn)
        if not df.empty:
            c = st.columns([1,1,1,1,1,1])
            c[0].markdown("**Symbol**"); c[3].markdown("TP"); c[4].markdown("SL")
            st.divider()
            for i, r in df.iterrows():
                try:
                    p = json.loads(r['params'])
                    c = st.columns([1,1,1,1,1,1])
                    c[0].markdown(f"**{r['symbol']}**")
                    c[1].caption(f"RSI<{p.get('rsi_trend')}")
                    c[2].caption(f"ADX>{p.get('adx_trend')}")
                    c[3].markdown(f"<span style='color:green'>+{p.get('target',0)*100:.1f}%</span>", unsafe_allow_html=True)
                    c[4].markdown(f"<span style='color:red'>-{p.get('stop',0)*100:.1f}%</span>", unsafe_allow_html=True)
                    if c[5].button("🗑️", key=f"d_{r['symbol']}"):
                        delete_strategy(r['symbol']); st.rerun()
                    st.markdown("<div class='strategy-row'></div>", unsafe_allow_html=True)
                except: pass
        else: st.info("No strategies.")

with t3:
    st.subheader("🕹️ Manual Trade Ticket")
    with st.form("manual"):
        c1,c2,c3,c4 = st.columns(4)
        sym = c1.text_input("Sym", "TSLA"); qty = c2.number_input("Qty", 1.0); side = c3.selectbox("Side", ["buy","sell"]); type = c4.selectbox("Type", ["market","limit","stop"])
        c5,c6,c7 = st.columns(3)
        lp = c5.number_input("Limit $", 0.0); sp = c6.number_input("Stop $", 0.0); tp = c7.number_input("Trail %", 0.0)
        if st.form_submit_button("🚀 Submit"):
            ok, m = broker.submit_manual_order(sym, qty, side, type, lp if lp>0 else None, sp if sp>0 else None, tp if tp>0 else None)
            if ok: st.success(m); time.sleep(1); st.rerun()
            else: st.error(m)

with t4:
    st.subheader("⚡ Live Trade Forensics")
    c1, c2 = st.columns([1,4]); auto = c1.checkbox("🔴 Live Monitor", True); c2.caption("Streams latency & fill data")
    
    ph = st.empty()
    while True:
        try: broker.sync_tca_logs()
        except: pass
        
        with sqlite3.connect(DB_PATH) as conn:
            df = pd.read_sql("SELECT * FROM trade_execution ORDER BY submitted_at DESC LIMIT 50", conn)
        
        with ph.container():
            if not df.empty:
                avg_api = df.head(5)['api_latency_ms'].mean()
                avg_fill = df.head(5)['fill_latency_ms'].mean()
                m1, m2 = st.columns(2)
                m1.metric("API Latency (Last 5)", f"{avg_api:.0f} ms")
                m2.metric("Fill Speed (Last 5)", f"{avg_fill:.0f} ms")
                
                disp = df[['submitted_at', 'symbol', 'side', 'order_type', 'api_latency_ms', 'fill_latency_ms', 'slippage_pct', 'status']].copy()
                disp.columns = ['Time', 'Sym', 'Side', 'Type', 'API(ms)', 'Fill(ms)', 'Slip%', 'Status']
                st.dataframe(disp.style.format({'API(ms)': '{:.0f}', 'Fill(ms)': '{:.0f}', 'Slip%': '{:.4f}%'}), use_container_width=True)
            else: st.info("No trades recorded yet.")
        
        if not auto: break
        time.sleep(2)

with t5:
    st.header("🔍 System Diagnostics")
    
    # 1. System Health
    st.subheader("1. System Health")
    c1, c2, c3 = st.columns(3)
    c1.metric("Container Hostname", socket.gethostname())
    c2.metric("Python Version", platform.python_version())
    
    # Check Heartbeat File
    hb_path = "/tmp/heartbeat"
    if os.path.exists(hb_path):
        last_beat = os.path.getmtime(hb_path)
        diff = time.time() - last_beat
        status = "✅ Alive" if diff < 60 else f"⚠️ Stalled ({int(diff)}s ago)"
        c3.metric("Heartbeat", status, delta=f"{int(diff)}s ago", delta_color="inverse")
    else:
        c3.metric("Heartbeat", "❌ Missing")

    st.divider()

    # 2. Environment Variables (Safe View)
    st.subheader("2. Environment Config")
    
    def mask_key(k):
        v = os.getenv(k)
        if not v: return "❌ Not Set"
        if len(v) < 8: return "******"
        return f"{v[:4]}...{v[-4:]} (Len: {len(v)})"

    env_cols = st.columns(2)
    with env_cols[0]:
        st.caption("🔑 Credentials Status")
        st.text_input("APIKEY (Live)", mask_key("APIKEY"), disabled=True)
        st.text_input("SECRETKEY (Live)", mask_key("SECRETKEY"), disabled=True)
        st.text_input("APIKEY_PAPER", mask_key("APIKEY_PAPER"), disabled=True)
        st.text_input("SECRETKEY_PAPER", mask_key("SECRETKEY_PAPER"), disabled=True)
    
    with env_cols[1]:
        st.caption("🌍 Endpoints")
        st.text_input("PAPER_URL", os.getenv("PAPER_URL", "Default"), disabled=True)
        st.text_input("LIVE_URL", os.getenv("LIVE_URL", "Default"), disabled=True)
        st.text_input("REPORT_LINK", mask_key("REPORT_LINK"), disabled=True)

    st.divider()

    # 3. Database Health
    st.subheader("3. Database Health")
    if os.path.exists(DB_PATH):
        size_kb = os.path.getsize(DB_PATH) / 1024
        st.write(f"📁 **DB Path:** `{DB_PATH}` ({size_kb:.1f} KB)")
        
        with sqlite3.connect(DB_PATH) as conn:
            try:
                tables = pd.read_sql("SELECT name FROM sqlite_master WHERE type='table'", conn)
                if not tables.empty:
                    st.caption("Table Row Counts:")
                    cols = st.columns(len(tables))
                    for idx, row in tables.iterrows():
                        tbl = row['name']
                        count = pd.read_sql(f"SELECT COUNT(*) as c FROM {tbl}", conn).iloc[0]['c']
                        cols[idx % len(cols)].metric(tbl, count)
                
                with st.expander("🔎 Inspect Raw Data Tables"):
                    sel_table = st.selectbox("Select Table", tables['name'].tolist())
                    st.dataframe(pd.read_sql(f"SELECT * FROM {sel_table} ORDER BY rowid DESC LIMIT 50", conn), use_container_width=True)
            except Exception as e:
                st.error(f"DB Read Error: {e}")
    else:
        st.error(f"❌ Database file not found at {DB_PATH}")

    st.divider()

    # 4. Network Diagnostics
    st.subheader("4. Network Diagnostics")
    if st.button("ping Alpaca API"):
        try:
            st.write("Pinging Alpaca...")
            start = time.time()
            broker.api.get_clock()
            latency = (time.time() - start) * 1000
            st.success(f"✅ Connection Successful! Latency: **{latency:.0f} ms**")
        except Exception as e:
            st.error(f"❌ Connection Failed: {e}")