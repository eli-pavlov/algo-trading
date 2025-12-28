import streamlit as st
import sqlite3
import json
import pandas as pd
import os

DB_PATH = os.getenv("DB_PATH", "/app/data/trading.db")

st.set_page_config(layout="wide", page_title="Algo Command Center")
st.title("⚡ Algo Command Center")

if not os.path.exists(DB_PATH):
    st.error(f"Database not found at {DB_PATH}. Wait for bot to initialize it.")
    st.stop()

conn = sqlite3.connect(DB_PATH)

# --- 1. PERFORMANCE METRICS ---
st.header("📈 Performance")
try:
    df_trades = pd.read_sql("SELECT * FROM trades ORDER BY timestamp DESC LIMIT 100", conn)
    if not df_trades.empty:
        total_trades = len(df_trades)
        # Simple placeholder metrics
        last_trade = df_trades.iloc[0]
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Trades", total_trades)
        col2.metric("Last Symbol", last_trade['symbol'])
        col3.metric("Last Price", f"${last_trade['price']:.2f}")
        
        st.dataframe(df_trades)
    else:
        st.info("No trades recorded yet.")
except Exception as e:
    st.error(f"Error reading trades: {e}")

# --- 2. STRATEGY MANAGEMENT ---
st.header("⚙️ Active Strategies")
try:
    df_strategies = pd.read_sql("SELECT * FROM strategies", conn)
    st.dataframe(df_strategies)
except Exception:
    st.warning("Strategies table not ready.")

# Add New Stock Form
st.subheader("Deploy New Strategy")
with st.form("add_stock"):
    col1, col2, col3 = st.columns(3)
    symbol = col1.text_input("Symbol (e.g. AAPL)").upper()
    strategy = col2.selectbox("Strategy", ["rsi_panic"])
    
    # JSON Params Editor
    default_params = json.dumps({
        "rsi_length": 14,
        "rsi_panic_threshold": 30,
        "qty": 1,
        "take_profit_pct": 0.05,
        "stop_loss_pct": 0.02,
        "timeframe": "2h"
    }, indent=2)
    
    params = col3.text_area("Parameters (JSON)", default_params, height=200)
    
    if st.form_submit_button("Deploy Bot"):
        if symbol and params:
            try:
                # Validate JSON
                parsed_params = json.loads(params) 
                c = conn.cursor()
                c.execute("INSERT OR REPLACE INTO strategies VALUES (?, ?, ?, 1)", 
                          (symbol, strategy, json.dumps(parsed_params)))
                conn.commit()
                st.success(f"Deployed {symbol} successfully!")
                st.rerun()
            except json.JSONDecodeError:
                st.error("Invalid JSON format in parameters.")
            except Exception as e:
                st.error(f"Database Error: {e}")
        else:
            st.warning("Please fill in Symbol.")

# Delete Strategy
with st.expander("🗑️ Remove Strategy"):
    del_symbol = st.text_input("Symbol to remove").upper()
    if st.button("Delete"):
        c = conn.cursor()
        c.execute("DELETE FROM strategies WHERE symbol=?", (del_symbol,))
        conn.commit()
        st.success(f"Removed {del_symbol}")
        st.rerun()

conn.close()