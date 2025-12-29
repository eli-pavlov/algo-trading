import streamlit as st
import pandas as pd
import sqlite3
import time
import json
import plotly.express as px  # NEW: For charts
from src.broker import Broker
from src.database import get_status, update_status, delete_strategy, DB_PATH

# 1. Page Config
st.set_page_config(page_title="Algo Command Center", layout="wide", page_icon="🛡️")

# --- CUSTOM CSS ---
st.markdown("""
<style>
    div.stButton > button { box-shadow: 0px 4px 0px #4a5568; transition: all 0.1s; border: 1px solid #cbd5e0; border-radius: 8px; font-weight: 600; }
    div.stButton > button:active { transform: translateY(4px); box-shadow: none; }
    .paper-badge { background-color: #fffbeb; color: #b7791f; padding: 8px; border: 2px dashed #ecc94b; text-align: center; font-weight: bold; margin-bottom: 15px; }
    .big-metric { font-size: 24px; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# 2. Broker Init
broker = Broker()
conn_status, conn_msg = broker.test_connection()

# 3. Sidebar
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
    c1, c2 = st.columns(2); c1.caption("1 Day"); c1.write(hist.get('1D')); c2.caption("1 Week"); c2.write(hist.get('1W'))
    
    st.markdown("---")
    engine_on = get_status("engine_running") == "1"
    if st.button("🛑 STOP ENGINE" if engine_on else "🚀 START ENGINE", use_container_width=True):
        update_status("engine_running", "0" if engine_on else "1")
        st.rerun()

# 4. Header
clock_msg = broker.get_market_clock()
if "🟢" in clock_msg: st.info(f"**{clock_msg}**")
else: st.warning(f"**{clock_msg}**")

# 5. Tabs (Added 5th Tab)
tab_assets, tab_strat, tab_manual, tab_tca, tab_debug = st.tabs(["📊 Assets", "⚙️ Strategies", "🕹️ Manual", "📉 Execution (TCA)", "🔍 Debug"])

# --- TAB 1: ASSETS ---
with tab_assets:
    try:
        positions = broker.api.list_positions()
        if positions:
            for p in positions:
                pl = float(p.unrealized_pl)
                with st.expander(f"{p.symbol} | {p.qty} sh | P/L: ${pl:.2f}"):
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Price", f"${float(p.current_price):.2f}")
                    c2.metric("Entry", f"${float(p.avg_entry_price):.2f}")
                    c3.metric("Day P/L", f"${float(p.unrealized_intraday_pl):.2f}")
                    c4.metric("Total P/L", f"${pl:.2f}")
        else: st.info("No active positions.")
    except Exception as e: st.error(str(e))

# --- TAB 2: STRATEGIES ---
with tab_strat:
    with sqlite3.connect(DB_PATH) as conn:
        df = pd.read_sql("SELECT * FROM strategies", conn)
        if not df.empty:
            cols = st.columns([1, 1, 1, 1, 1, 1])
            cols[0].markdown("**Symbol**"); cols[3].markdown("TP"); cols[4].markdown("SL")
            st.divider()
            for i, row in df.iterrows():
                try:
                    p = json.loads(row['params'])
                    c = st.columns([1, 1, 1, 1, 1, 1])
                    c[0].markdown(f"**{row['symbol']}**")
                    c[1].caption(f"RSI < {p.get('rsi_trend')}")
                    c[2].caption(f"ADX > {p.get('adx_trend')}")
                    c[3].markdown(f"<span style='color:green'>+{p.get('target',0)*100:.1f}%</span>", unsafe_allow_html=True)
                    c[4].markdown(f"<span style='color:red'>-{p.get('stop',0)*100:.1f}%</span>", unsafe_allow_html=True)
                    if c[5].button("🗑️", key=f"d_{row['symbol']}"):
                        delete_strategy(row['symbol']); st.rerun()
                    st.markdown("<hr style='margin:5px 0'>", unsafe_allow_html=True)
                except: pass
        else: st.info("No active strategies.")

# --- TAB 3: MANUAL ---
with tab_manual:
    with st.form("manual"):
        c1, c2, c3, c4 = st.columns(4)
        sym = c1.text_input("Sym", "TSLA"); qty = c2.number_input("Qty", 1.0); side = c3.selectbox("Side", ["buy","sell"]); type = c4.selectbox("Type", ["market","limit","stop"])
        if st.form_submit_button("Submit"):
            ok, msg = broker.submit_manual_order(sym, qty, side, type)
            if ok: st.success(msg); time.sleep(1); st.rerun()
            else: st.error(msg)

# --- TAB 4: TCA (NEW) ---
with tab_tca:
    st.subheader("📉 Transaction Cost Analysis")
    
    # 1. Sync Button (Trigger syncing with Alpaca)
    if st.button("🔄 Sync Trade Logs", use_container_width=True):
        with st.spinner("Fetching fill data from Alpaca..."):
            broker.sync_tca_logs()
            st.success("Sync Complete")
            time.sleep(1)
            st.rerun()

    # 2. Fetch Data
    with sqlite3.connect(DB_PATH) as conn:
        df_tca = pd.read_sql("SELECT * FROM trade_execution ORDER BY submitted_at DESC", conn)
    
    if not df_tca.empty:
        # 3. Summary Metrics
        filled = df_tca[df_tca['status'] == 'FILLED']
        
        m1, m2, m3 = st.columns(3)
        total_trades = len(filled)
        avg_slip = filled['slippage_pct'].mean() if not filled.empty else 0.0
        
        m1.metric("Total Fills", total_trades)
        m2.metric("Avg Slippage", f"{avg_slip:.4f}%", delta=-avg_slip, delta_color="inverse")
        m3.caption("Positive Slippage = You paid more than expected (Cost).")

        st.divider()

        # 4. Visual Analysis (Slippage over time)
        if total_trades > 0:
            filled['submitted_at'] = pd.to_datetime(filled['submitted_at'])
            fig = px.scatter(filled, x="submitted_at", y="slippage_pct", 
                             color="side", size="qty", 
                             title="Slippage Distribution (Bubble Size = Qty)",
                             labels={"slippage_pct": "Slippage (%)", "submitted_at": "Time"})
            st.plotly_chart(fig, use_container_width=True)

        # 5. Raw Data Table
        st.markdown("### Trade Logs")
        st.dataframe(df_tca.style.format({
            "snapshot_price": "${:.2f}", 
            "fill_price": "${:.2f}",
            "slippage_pct": "{:.4f}%"
        }), use_container_width=True)
    else:
        st.info("No trade data recorded yet. Place a trade to see analysis.")

# --- TAB 5: DEBUG ---
with tab_debug:
    st.json({"DB": DB_PATH, "API": conn_status})