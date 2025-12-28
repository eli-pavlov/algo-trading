import streamlit as st
import sqlite3
import json
import pandas as pd

DB_PATH = "/app/data/trading.db"

st.set_page_config(layout="wide")
st.title("⚡ Algo Command Center")

# --- 1. PERFORMANCE METRICS ---
conn = sqlite3.connect(DB_PATH)
df_trades = pd.read_sql("SELECT * FROM trades ORDER BY timestamp DESC", conn)
if not df_trades.empty:
    success_rate = len(df_trades[df_trades['slippage'] > -0.1]) / len(df_trades) # Placeholder logic
    avg_slippage = df_trades['slippage'].mean()
    
    col1, col2 = st.columns(2)
    col1.metric("Success Rate", f"{success_rate:.1%}")
    col2.metric("Avg Slippage", f"{avg_slippage:.2f}%")
    st.dataframe(df_trades)

# --- 2. STRATEGY MANAGEMENT ---
st.header("⚙️ Active Strategies")
df_strategies = pd.read_sql("SELECT * FROM strategies", conn)
st.dataframe(df_strategies)

# Add New Stock Form
with st.form("add_stock"):
    col1, col2, col3 = st.columns(3)
    symbol = col1.text_input("Symbol (e.g. AAPL)")
    strategy = col2.selectbox("Strategy", ["rsi_panic", "macd"])
    
    # JSON Params Editor
    default_params = '{"threshold": 30, "qty": 1, "stop_loss": 0.02}'
    params = col3.text_area("Parameters (JSON)", default_params)
    
    if st.form_submit_button("Deploy Bot"):
        try:
            # Validate JSON
            json.loads(params) 
            c = conn.cursor()
            c.execute("INSERT OR REPLACE INTO strategies VALUES (?, ?, ?, 1)", 
                      (symbol, strategy, params))
            conn.commit()
            st.success(f"Deployed {symbol}!")
            st.experimental_rerun()
        except Exception as e:
            st.error(f"Error: {e}")

conn.close()