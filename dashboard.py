import streamlit as st
import pandas as pd
import psycopg2
import plotly.express as px
import os

st.set_page_config(page_title="Krafix FactoryOS", layout="wide")

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5435")
DB_USER = os.getenv("POSTGRES_USER", "postgres")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "password")
DB_NAME = os.getenv("POSTGRES_DB", "krafix_factory")

def get_db_connection():
    try:
        return psycopg2.connect(f"dbname={DB_NAME} user={DB_USER} password={DB_PASS} host={DB_HOST} port={DB_PORT}")
    except:
        return None

conn = get_db_connection()

if conn:
    st.title("🏭 Krafix Command Center")
    
    try:
        cur = conn.cursor()
        
        # 1. Auto-create table if missing (Same schema as server.py)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS production_logs (
                id SERIAL PRIMARY KEY, machine_id TEXT, rolls_produced INT, timestamp TIMESTAMP DEFAULT NOW()
            );
        """)
        conn.commit()

        # 2. Fetch Data (Using Cursor to avoid Pandas/SQLAlchemy warning)
        cur.execute("SELECT SUM(rolls_produced) FROM production_logs WHERE date(timestamp) = CURRENT_DATE;")
        result = cur.fetchone()
        prod_today = result[0] if result and result[0] is not None else 0
        
        # Charts
        col1, col2 = st.columns(2)
        col1.metric("📦 Production Today", f"{prod_today} Rolls")
        
        # Trend Chart
        cur.execute("SELECT date(timestamp) as dt, SUM(rolls_produced) as rolls FROM production_logs GROUP BY dt ORDER BY dt ASC")
        rows = cur.fetchall()
        
        if rows:
            df_trend = pd.DataFrame(rows, columns=['dt', 'rolls'])
            fig = px.bar(df_trend, x='dt', y='rolls', template="plotly_dark", title="Daily Production")
            st.plotly_chart(fig, width="stretch")
        else:
            st.info("No production history yet. Start logging via WhatsApp!")
            
        cur.close()
        
    except Exception as e:
        st.error(f"Error loading dashboard: {e}")
    
    conn.close()
else:
    st.error("Connecting to Database...")

if st.button("Refresh"): st.rerun()