# dashboard.py
import streamlit as st
import pandas as pd
import psycopg2
import plotly.express as px
import time

st.set_page_config(page_title="Krafix FactoryOS", page_icon="🏭", layout="wide")

def get_db_connection():
    return psycopg2.connect("dbname=krafix_factory user=postgres password=password")

# METRICS
conn = get_db_connection()
prod_today = pd.read_sql("SELECT SUM(rolls_produced) FROM production_logs WHERE date(timestamp) = CURRENT_DATE;", conn).iloc[0,0] or 0
low_stock = pd.read_sql("SELECT COUNT(*) FROM inventory WHERE quantity < 50;", conn).iloc[0,0]
conn.close()

st.title("🏭 Krafix Command Center")
col1, col2, col3 = st.columns(3)
col1.metric("📦 Production Today", f"{prod_today} Rolls")
col2.metric("⚠️ Low Stock", f"{low_stock} Items", delta_color="inverse")
col3.metric("⚡ Energy Cost", "₹ 420")

# CHARTS
st.subheader("📈 Production Trend")
conn = get_db_connection()
df_trend = pd.read_sql("SELECT date(timestamp), SUM(rolls_produced) as rolls FROM production_logs GROUP BY date(timestamp)", conn)
fig = px.bar(df_trend, x='date', y='rolls', template="plotly_dark", color='rolls')
st.plotly_chart(fig, use_container_width=True)

# AUTO REFRESH
if st.button("Refresh"): st.rerun()