import streamlit as st
import pandas as pd
import sqlite3
import os
import plotly.express as px

st.set_page_config(page_title="Deep Seek Terminal", layout="wide")
DB_PATH = os.getenv("DB_PATH", "data/trading.db")

def load_data(query):
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql(query, conn)

st.title("🛡️ Algo Command Center")

if st.sidebar.button("🧠 Manual AI Re-Optimization"):
    import subprocess
    subprocess.run(["python", "src/analyzer.py"])
    st.sidebar.success("Intelligence Updated!")

tab1, tab2 = st.tabs(["📈 Performance", "⚙️ Strategies"])

with tab1:
    st.subheader("Account Growth")
    # Pull equity history from DB
    try:
        df = load_data("SELECT * FROM equity_history")
        st.plotly_chart(px.line(df, x='timestamp', y='balance'))
    except: st.info("Waiting for trade data...")

with tab2:
    st.subheader("Active Logic Settings")
    try:
        df_strat = load_data("SELECT * FROM strategies")
        st.table(df_strat)
    except: st.warning("No strategies in database.")