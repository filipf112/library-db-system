import oracledb
import pandas as pd
import streamlit as st
from .config import DATABASES, DB_PASSWORD

def get_connection(db_choice):
    conf = DATABASES.get(db_choice)
    if not conf:
        return None
    try:
        return oracledb.connect(
            user=conf["user"],
            password=DB_PASSWORD,
            dsn=conf["dsn"]
        )
    except Exception as e:
        st.error(f"Connection error: {e}")
        return None

def run_query(conn, query, params=None):
    if params is None:
        params = {}
    df = pd.read_sql(query, conn, params=params)
    
    # Data cleaning for presentation
    for col in ['ROK_WYDANIA', 'ID_KSIAZKI', 'ID_FILII']:
        if col in df.columns:
            df[col] = df[col].fillna(0).astype(int).astype(str).str.replace(',', '')
    return df

def run_transaction(conn, sql_statements, params_list):
    """Executes atomic transaction with commit/rollback."""
    cursor = conn.cursor()
    try:
        for sql, params in zip(sql_statements, params_list):
            cursor.execute(sql, params)
        conn.commit()
        return True, "Transaction successful."
    except Exception as e:
        conn.rollback()
        return False, f"Transaction failed: {e}"
    finally:
        cursor.close()