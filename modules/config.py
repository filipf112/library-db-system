import streamlit as st

# Load password from secrets manager
DB_PASSWORD = st.secrets["database"]["password"]

DATABASES = {
    "FILIA 1 (Linux)": {
        "user": "BIBLIOTEKA",
        "dsn": "192.168.56.101:1521/FREEPDB1",
        "id": 1
    },
    "FILIA 2 (Windows)": {
        "user": "BIBLIOTEKA",
        "dsn": "192.168.56.1:1521/freepdb1",
        "id": 2
    }
}