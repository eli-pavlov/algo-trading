import streamlit as st
import pandas as pd
import sqlite3
import time
import json
from src.broker import Broker
from src.database import get_status, update_status, delete_strategy, DB_PATH

# 1. Page Config
st.set_page_config(page_title="Algo Command Center", layout="wide", page_icon="🛡️")

# CSS for compact metrics
st.markdown("""
<style>
    .stMetric {
        background-color: #f0f2f6;
        padding: 10px;
        border-radius: 5px;
    }
    .compact-text {
        font-size: 0.8rem;
        color: #555;
    }
    .strategy-card {
        padding: 10px;
        border-bottom: 1px solid #ddd;
    }
</style>
""", unsafe_allow_html=True)

# 2. Broker Init
broker = Broker()
conn_status, conn_msg = broker.test_connection()

# 3. Sidebar
with st.sidebar:
    st.title("📡 Overview")
    if conn_status:
        st.success("🟢 API ONLINE")
    else:
        st.error("🔴 DISCONNECTED")
        
    st.markdown("---")
    acc = broker.get_account_stats()
    st.metric("Buying Power", f"${acc.get('Power', 0):,.2f}")
    st.metric("Cash", f"${acc.get('Cash', 0):,.2f}")
    
    st.markdown("---")
    hist = broker.get_portfolio_history_stats()
    st.metric("Total Equity", f"${acc.get('Equity', 0):,.2f}")
    
    c1, c2 = st.columns(2)
    c1.caption("1 Day"); c1.write(hist.get('1D', 'N/A'))
    c2.caption("1 Week"); c2.write(hist.get('1W', 'N/A'))
    
    st.markdown("---")
    engine_on = get_status("engine_running") == "1"
    if st.button("🛑 STOP" if engine_on else "🚀 START", use_container_width=True, type="primary" if not engine_on else "secondary"):
        update_status("engine_running", "0" if engine_on else "1")
        st.rerun()

# 4. Header
clock_msg = broker.get_market_clock()
if "🟢" in clock_msg:
    st.info(f"**{clock_msg}**")
else:
    st.warning(f"**{clock_msg}**")

# 5. Tabs
tab_assets, tab_strat, tab_manual, tab_debug = st.tabs(["📊 Assets", "⚙️ Strategies", "🕹️ Manual", "🔍 Debug"])

# --- TAB 1: ASSETS ---
with tab_assets:
    try:
        positions = broker.api.list_positions()
        if positions:
            for p in positions:
                pl_total = float(p.unrealized_pl)
                with st.expander(f"{p.symbol} | {p.qty} sh | P/L: ${pl_total:.2f}"):
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Price", f"${float(p.current_price):.2f}")
                    c2.metric("Entry", f"${float(p.avg_entry_price):.2f}")
                    c3.metric("Day P/L", f"${float(p.unrealized_intraday_pl):.2f}")
                    c4.metric("Total P/L", f"${pl_total:.2f}")
                    
                    orders = broker.get_orders_for_symbol(p.symbol)
                    if orders:
                        st.caption("Active Orders:")
                        for o in orders: st.code(o, language="text")
        else:
            st.info("No active positions.")
    except Exception as e:
        st.error(f"Error: {e}")

# --- TAB 2: STRATEGIES (COMPACT & FRIENDLY) ---
with tab_strat:
    with sqlite3.connect(DB_PATH) as conn:
        try:
            df = pd.read_sql("SELECT * FROM strategies", conn)
            if not df.empty:
                # Header Row
                h1, h2, h3, h4, h5, h6 = st.columns([1, 1, 1, 1, 1, 1])
                h1.markdown("**Symbol**")
                h2.markdown("<small>RSI Limit</small>", unsafe_allow_html=True)
                h3.markdown("<small>ADX Min</small>", unsafe_allow_html=True)
                h4.markdown("<small>Take Profit</small>", unsafe_allow_html=True)
                h5.markdown("<small>Stop Loss</small>", unsafe_allow_html=True)
                h6.markdown("") # Action
                st.divider()

                for index, row in df.iterrows():
                    c1, c2, c3, c4, c5, c6 = st.columns([1, 1, 1, 1, 1, 1])
                    
                    try:
                        p = json.loads(row['params'])
                        
                        # Symbol
                        c1.markdown(f"##### {row['symbol']}")
                        
                        # Metrics (Small text)
                        c2.markdown(f"{p.get('rsi_trend', '-')}")
                        c3.markdown(f"{p.get('adx_trend', '-')}")
                        
                        # Percentages colored
                        tp = p.get('target', 0) * 100
                        sl = p.get('stop', 0) * 100
                        c4.markdown(f"<span style='color:green'>+{tp:.1f}%</span>", unsafe_allow_html=True)
                        c5.markdown(f"<span style='color:red'>-{sl:.1f}%</span>", unsafe_allow_html=True)
                        
                        # Delete (Icon only button)
                        if c6.button("🗑️", key=f"del_{row['symbol']}", help="Remove Strategy"):
                            delete_strategy(row['symbol'])
                            st.rerun()
                            
                    except:
                        c2.warning("Error")
                    
                    st.markdown("<hr style='margin: 5px 0; border-top: 1px solid #eee;'>", unsafe_allow_html=True)

            else:
                st.info("No strategies active.")
        except Exception as e:
            st.error(f"DB Error: {e}")

# --- TAB 3: MANUAL ---
with tab_manual:
    with st.form("manual_trade"):
        c1, c2, c3 = st.columns(3)
        sym = c1.text_input("Symbol", "TSLA").upper()
        qty = c2.number_input("Qty", 0.1, 1000.0, 1.0)
        side = c3.selectbox("Side", ["buy", "sell"])
        
        c4, c5 = st.columns(2)
        type = c4.selectbox("Type", ["market", "limit", "stop", "trailing_stop"])
        px = c5.number_input("Price/Trail%", 0.0)
        
        if st.form_submit_button("Submit Order"):
            l_px = px if type == 'limit' else None
            s_px = px if type == 'stop' else None
            t_pct = px if type == 'trailing_stop' else None
            
            ok, msg = broker.submit_manual_order(sym, qty, side, type, l_px, s_px, t_pct)
            if ok: st.success(msg); time.sleep(1); st.rerun()
            else: st.error(msg)

# --- TAB 4: DEBUG ---
with tab_debug:
    st.json({"DB": DB_PATH, "API": conn_status, "Engine": engine_on, "Msg": conn_msg})