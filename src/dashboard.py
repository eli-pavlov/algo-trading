import streamlit as st
import pandas as pd
import sqlite3
import time
import json
from src.broker import Broker
from src.database import get_status, update_status, delete_strategy, DB_PATH

# 1. Page Config
st.set_page_config(page_title="Algo Command Center", layout="wide", page_icon="🛡️")

# --- CUSTOM CSS: 3D Buttons & Paper Badge ---
st.markdown("""
<style>
    /* 3D Button Styling */
    div.stButton > button {
        box-shadow: 0px 4px 0px #4a5568; 
        transition: all 0.1s;
        border: 1px solid #cbd5e0;
        border-radius: 8px;
        transform: translateY(0);
        font-weight: 600;
    }
    
    div.stButton > button:active {
        transform: translateY(4px); 
        box-shadow: 0px 0px 0px #4a5568;
    }

    div.stButton > button:hover {
        border-color: #3182ce;
        color: #2b6cb0;
    }

    /* Metric Cards */
    .stMetric {
        background-color: #f7fafc;
        padding: 10px;
        border-radius: 8px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }

    /* Paper Trading Warning Badge */
    .paper-badge {
        background-color: #fffbeb; 
        color: #b7791f; 
        padding: 8px;
        border-radius: 6px;
        border: 2px dashed #ecc94b;
        text-align: center;
        font-weight: bold;
        margin-bottom: 15px;
        text-transform: uppercase;
        letter-spacing: 1px;
        font-size: 0.85rem;
    }
    
    /* Strategy Row Styling */
    .strategy-row {
        padding: 8px 0;
        border-bottom: 1px solid #eee;
    }
</style>
""", unsafe_allow_html=True)

# 2. Broker Init
broker = Broker()
conn_status, conn_msg = broker.test_connection()

# 3. Sidebar
with st.sidebar:
    # PAPER TRADING BADGE
    st.markdown('<div class="paper-badge">⚠️ Alpaca Paper Trading</div>', unsafe_allow_html=True)
    
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
    
    # 4-Grid Layout for Timeframes
    c1, c2 = st.columns(2)
    c1.caption("1 Day"); c1.write(hist.get('1D', 'N/A'))
    c2.caption("1 Week"); c2.write(hist.get('1W', 'N/A'))
    
    c3, c4 = st.columns(2)
    c3.caption("1 Month"); c3.write(hist.get('1M', 'N/A'))
    c4.caption("1 Year"); c4.write(hist.get('1A', 'N/A'))
    
    st.markdown("---")
    engine_on = get_status("engine_running") == "1"
    if st.button("🛑 STOP ENGINE" if engine_on else "🚀 START ENGINE", use_container_width=True):
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

# --- TAB 2: STRATEGIES ---
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
                h6.markdown("") 
                st.divider()

                for index, row in df.iterrows():
                    c1, c2, c3, c4, c5, c6 = st.columns([1, 1, 1, 1, 1, 1])
                    
                    try:
                        p = json.loads(row['params'])
                        
                        # Symbol
                        c1.markdown(f"**{row['symbol']}**")
                        
                        # Metrics 
                        c2.markdown(f"<small>{p.get('rsi_trend', '-')}</small>", unsafe_allow_html=True)
                        c3.markdown(f"<small>{p.get('adx_trend', '-')}</small>", unsafe_allow_html=True)
                        
                        # Percentages 
                        tp = p.get('target', 0) * 100
                        sl = p.get('stop', 0) * 100
                        c4.markdown(f"<span style='color:green; font-weight:bold'>+{tp:.1f}%</span>", unsafe_allow_html=True)
                        c5.markdown(f"<span style='color:red; font-weight:bold'>-{sl:.1f}%</span>", unsafe_allow_html=True)
                        
                        # Delete
                        if c6.button("🗑️", key=f"del_{row['symbol']}", help="Remove Strategy"):
                            delete_strategy(row['symbol'])
                            st.toast(f"Removed {row['symbol']}")
                            time.sleep(0.5)
                            st.rerun()
                            
                    except:
                        c2.warning("Error")
                    
                    st.markdown("<div class='strategy-row'></div>", unsafe_allow_html=True)

            else:
                st.info("No strategies active. Run the scanner to populate.")
        except Exception as e:
            st.error(f"DB Error: {e}")

# --- TAB 3: MANUAL CONTROL (Restored Distinct Inputs) ---
with tab_manual:
    st.subheader("🕹️ Manual Trade Ticket")
    
    with st.form("manual_trade"):
        # Top Row: Basic Info
        c1, c2, c3, c4 = st.columns(4)
        sym = c1.text_input("Symbol", "TSLA").upper()
        qty = c2.number_input("Qty", 0.1, 10000.0, 1.0)
        side = c3.selectbox("Side", ["buy", "sell"])
        type = c4.selectbox("Order Type", ["market", "limit", "stop", "stop_limit", "trailing_stop"])
        
        st.markdown("---")
        
        # Bottom Row: Advanced Inputs (Clearly Separated)
        st.caption("Order Details (Fill based on Order Type)")
        c5, c6, c7 = st.columns(3)
        limit_px = c5.number_input("Limit Price ($)", 0.0, help="Required for Limit and Stop-Limit orders")
        stop_px = c6.number_input("Stop Price ($)", 0.0, help="Required for Stop and Stop-Limit orders")
        trail_pct = c7.number_input("Trail Percent (%)", 0.0, help="Required for Trailing Stop orders")
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        if st.form_submit_button("🚀 Submit Order", type="primary"):
            # Logic to filter inputs
            l_px = limit_px if type in ['limit', 'stop_limit'] else None
            s_px = stop_px if type in ['stop', 'stop_limit'] else None
            t_pct = trail_pct if type == 'trailing_stop' else None
            
            ok, msg = broker.submit_manual_order(sym, qty, side, type, l_px, s_px, t_pct)
            if ok: 
                st.success(f"✅ {msg}")
                time.sleep(1)
                st.rerun()
            else: 
                st.error(f"❌ {msg}")

# --- TAB 4: DEBUG ---
with tab_debug:
    st.json({"DB": DB_PATH, "API": conn_status, "Engine": engine_on, "Msg": conn_msg})