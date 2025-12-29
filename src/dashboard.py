import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import os

# --- 1. SETTINGS ---
DB_PATH = "trading.db"
st.set_page_config(page_title="Deep Seek Terminal", layout="wide")

# --- 2. DATABASE HELPER ---
def load_data(table):
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql(f"SELECT * FROM {table}", conn)

# --- 3. UI LAYOUT ---
st.title("🛡️ Deep Seek Terminal")
st.sidebar.header("Command Center")

if st.sidebar.button("🧠 Run AI Re-Optimization"):
    with st.spinner("Analyzing Market Regimes..."):
        # This triggers your analyzer logic
        import subprocess
        subprocess.run(["python", "analyzer.py"])
        st.success("Intelligence Updated!")

# --- 4. DASHBOARD TABS ---
tab1, tab2, tab3 = st.tabs(["📈 Portfolio", "📋 Live Strategy", "📜 Trade History"])

with tab1:
    st.subheader("Total Equity (2025)")
    # Mock data - in prod, pull from a 'balance_history' table
    df_perf = pd.DataFrame({"Date": ["Jan", "Feb", "Mar"], "Balance": [2500, 2750, 3100]})
    fig = px.line(df_perf, x="Date", y="Balance", markers=True, title="Portfolio Growth")
    st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.subheader("Active Bot Settings")
    try:
        df_strat = load_data("strategies")
        st.dataframe(df_strat, use_container_width=True)
    except:
        st.info("No active strategies found. Run the Analyzer first.")

with tab3:
    st.subheader("Recent Executions")
    # This shows every Buy/Sell the daemon has made
    st.info("Connecting to live Alpaca history...")