import streamlit as st
import pandas as pd
import sqlite3
import time
import psutil
from datetime import datetime
from src.broker import Broker
from src.config import Config
from src.database import get_status, update_status, get_strategies, DB_PATH
from src.notifications import send_trade_notification 

st.set_page_config(page_title="Algo Command Center", layout="wide")

# --- CSS ---
st.markdown("""
<style>
    [data-testid="stVerticalBlock"] { gap: 0.2rem !important; }
    .stMetric { padding: 2px !important; }
    [data-testid="stMetricValue"] { font-size: 1.2rem !important; }
    [data-testid="stMetricLabel"] { font-size: 0.8rem !important; }
    .asset-card { background-color: #ffffff; border: 1px solid #e0e0e0; border-radius: 8px; padding: 10px; margin-bottom: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
    .dark-mode .asset-card { background-color: #262730; border: 1px solid #41444e; }
    .order-chip { display: inline-block; font-family: monospace; font-size: 0.85rem; background-color: #f0f2f6; color: #31333F; padding: 2px 8px; border-radius: 4px; margin-right: 8px; margin-top: 4px; border: 1px solid #d0d0d0; }
    .dark-mode .order-chip { background-color: #363945; color: #FAFAFA; border: 1px solid #555; }
    .order-label { font-weight: bold; color: #555; }
    .debug-card { background: #f0f2f6; padding: 6px; border-radius: 4px; font-family: monospace; font-size: 11px; margin-bottom: 5px;}
    .ticker-logo { width: 32px; height: 32px; vertical-align: middle; margin-right: 10px; border-radius: 50%; background-color: #fff; padding: 2px; border: 1px solid #eee; }
</style>
""", unsafe_allow_html=True)

# Initialize Broker
broker = Broker()

# --- 1. SIDEBAR & AUTO-REFRESH ---
conn_ok, conn_msg = broker.test_connection()
with st.sidebar:
    st.markdown(f"**MODE: {Config.MODE}**")
    
    # 🔄 AUTO-REFRESH TOGGLE
    # This creates a loop effect. If checked, the script waits 30s then reruns.
    auto_refresh = st.checkbox("🔄 Live Updates (30s)", value=True)
    
    if conn_ok:
        st.success("🟢 API ONLINE")
        acc = broker.get_account_stats()
        st.metric("Equity", f"${acc.get('Equity', 0):,.0f}")
        st.metric("Power", f"${acc.get('Power', 0):,.0f}")
        
        st.markdown("---")
        st.caption("24H Equity Curve")
        try:
            from alpaca.trading.requests import GetPortfolioHistoryRequest
            hist = broker.client.get_portfolio_history(GetPortfolioHistoryRequest(period="1D", timeframe="15Min"))
            if hist and hist.equity:
                clean_equity = [x if x is not None else 0 for x in hist.equity]
                st.area_chart(pd.DataFrame({"Equity": clean_equity}), height=100, color="#29b5e8")
        except: st.caption("Graph unavailable")
    else:
        st.error(f"🔴 DISCONNECTED: {conn_msg}")

    st.divider()
    eng = get_status("engine_running") == "1"
    if st.button("🛑 STOP" if eng else "🚀 START", use_container_width=True):
        update_status("engine_running", "0" if eng else "1"); st.rerun()

# --- 2. MARKET CLOCK ---
clock_status = broker.get_market_clock()
mc_col1, mc_col2 = st.columns([3, 1])
with mc_col1:
    if "Closed" in clock_status: st.error(f"**{clock_status}**", icon="🔴")
    elif "Open" in clock_status: st.success(f"**{clock_status}**", icon="🟢")
    else: st.warning(f"**{clock_status}**", icon="🟠")
with mc_col2:
    if st.button("🔄 Refresh", key="top_refresh"): st.rerun()

# --- 3. TABS ---
t1, t2, t3, t4, t5 = st.tabs(["📊 Assets", "⚙️ Strategies", "🕹️ Manual", "📉 Execution", "🔍 Debug"])

with t1: # ASSETS
    positions = broker.get_all_positions()
    if positions:
        positions.sort(key=lambda x: float(x.market_value), reverse=True)
        for p in positions:
            symbol = p.symbol
            qty = float(p.qty)
            curr_price = float(p.current_price)
            pl_val = float(p.unrealized_pl)
            pl_pct = float(p.unrealized_plpc) * 100
            mkt_val = float(p.market_value)
            
            # Orders
            open_orders = broker.get_orders_for_symbol(symbol)
            order_html_list = []
            if open_orders:
                for o in open_orders:
                    trigger = o.limit_price or o.stop_price
                    trigger_val = float(trigger) if trigger else 0.0
                    
                    dist_str = ""
                    if trigger_val > 0 and curr_price > 0:
                        dist = -1 * ((trigger_val - curr_price) / curr_price) * 100
                        dist_str = f" <span style='color:{'#28a745' if dist>0 else '#dc3545'}'>({dist:+.1f}%)</span>"
                    
                    lbl = o.order_type.upper()
                    if o.side == 'sell':
                        if trigger_val > curr_price: lbl = "🎯 TP" 
                        elif trigger_val < curr_price: lbl = "🛑 SL" 
                    
                    price_display = f"${trigger_val:.2f}" if trigger_val > 0 else "MKT"
                    chip = f"<span class='order-chip'><b>{lbl}</b>: {price_display}{dist_str}</span>"
                    order_html_list.append(chip)
            else:
                order_html_list.append("<span style='color:#888; font-style:italic; font-size:0.8rem;'>No pending orders</span>")

            orders_html = "".join(order_html_list)
            logo_url = f"https://s3-symbol-logo.tradingview.com/{symbol.lower()}.svg"
            
            with st.container(border=True):
                c1, c2, c3, c4, c5 = st.columns([1.5, 1, 1, 1, 1.2])
                c1.markdown(f"""
                    <div style="display:flex; align-items:center;">
                        <img src="{logo_url}" class="ticker-logo" onerror="this.style.display='none'">
                        <h3 style="margin:0; padding:0;">{symbol}</h3>
                    </div>
                """, unsafe_allow_html=True)
                c2.metric("Qty", f"{qty:.1f}")
                c3.metric("Price", f"${curr_price:.2f}")
                delta_str = f"{'+' if pl_val >= 0 else '-'}${abs(pl_val):.2f}"
                c4.metric("P/L", f"{pl_pct:+.2f}%", delta_str)
                c5.metric("Value", f"${mkt_val:,.0f}")
                st.markdown(f"""<div style="margin-top: -10px; margin-bottom: 5px;">{orders_html}</div>""", unsafe_allow_html=True)
    else: st.info("No active positions.")

with t2: # STRATEGIES
    st.subheader("Active Strategy Configurations")
    try:
        strategies = get_strategies()
        if strategies:
            display_data = []
            for ticker, params in strategies.items():
                display_data.append({
                    "Ticker": ticker,
                    "Target (TP)": f"{params.get('target', 0)*100:.1f}%",
                    "Stop (SL)": f"{params.get('stop', 0)*100:.1f}%",
                    "RSI Thresh": params.get('rsi_trend', 'N/A'),
                    "ADX Thresh": params.get('adx_trend', 'N/A')
                })
            st.dataframe(pd.DataFrame(display_data), use_container_width=True, hide_index=True)
        else:
            st.warning("No strategies found. Run the Tuner.")
            if st.button("Run Tuner Now"):
                st.info("Please run: docker exec algo_heart python src/tuner.py")
    except Exception as e: st.error(f"DB Error: {e}")

with t3: # MANUAL TICKET
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
            if ok: 
                st.success(f"Sent: {res}")
                try:
                    send_trade_notification()
                    st.toast("Slack Notification Sent!", icon="🔔")
                except Exception as e:
                    st.warning(f"Order sent, but notification failed: {e}")
                time.sleep(1.5)
                st.rerun()
            else: st.error(res)

with t4: # EXECUTION
    st.subheader("⚡ Persistent History")
    with sqlite3.connect(DB_PATH) as conn:
        try:
            df = pd.read_sql("SELECT * FROM trade_execution ORDER BY submitted_at DESC", conn)
            st.dataframe(df, use_container_width=True, height=450)
        except: st.info("No records found.")

with t5: # DEBUG
    st.header("🔍 System Diagnostics")
    r1, r2, r3 = st.columns(3)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    r1.metric("RAM Usage", f"{mem.percent}%", f"{mem.used//1024**2}MB Used")
    disk_color = "normal" if disk.percent < 85 else "inverse"
    r2.metric("Disk Space", f"{disk.free//1024**3}GB Free", f"{disk.percent}% Used", delta_color=disk_color)
    avg_lat = broker.get_mean_latency_24h()
    r3.metric("Avg Latency (24h)", f"{avg_lat:.1f}ms")
    st.divider()
    act_key, _, is_paper = Config.get_auth()
    st.markdown(f"""<div class="debug-card">
        <b>Active Mode:</b> {Config.MODE}<br>
        <b>In-Use Key:</b> {act_key[:4]}...{act_key[-4:]}<br>
        <b>Target Endpoint:</b> {"Paper Simulator" if is_paper else "Live Exchange"}
    </div>""", unsafe_allow_html=True)

# --- AUTO REFRESH LOGIC ---
if auto_refresh:
    time.sleep(30)
    st.rerun()