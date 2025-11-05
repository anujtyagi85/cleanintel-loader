import streamlit as st
import pandas as pd
import requests
import plotly.express as px
import os
from streamlit_authenticator import Authenticate

st.set_page_config(page_title="CleanIntel Loader", layout="wide")

# ---------------- AUTH SETUP ---------------- #

credentials = {
    "usernames": {
        "anuj.tyagi074@gmail.com": {
            "name": "Anuj Tyagi",
            "password": "$2b$12$VyDmP7Z6wtogzbHaxkHE7ugjrvByB1e2RI/ThV7nZbKPqu.3SbZWW"
        }
    }
}

authenticator = Authenticate(
    credentials,
    cookie_name="cleanintel_cookie",
    key="abcdef",
    cookie_expiry_days=30
)

name, authentication_status, username = authenticator.login()

if authentication_status is False:
    st.error("Username/Password is incorrect")

if authentication_status is None:
    st.warning("Please login first.")

# stop page if not logged in
if authentication_status != True:
    st.stop()

# ---------------- AFTER LOGIN UI ---------------- #

authenticator.logout("Logout", "sidebar")
st.sidebar.write(f"Logged in as: {name}")

st.title("CleanIntel Loader")

uploaded_file = st.file_uploader("Upload CSV File", type=["csv"])

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)
    st.write("Data Preview")
    st.dataframe(df)

    # show columns
    st.write("Columns detected:")
    st.write(df.columns.tolist())

    # show basic metrics
    st.write("Row count:", len(df))
    st.write("Column count:", len(df.columns))

    # Sample simple visualization if numeric exists
    num_cols = df.select_dtypes(include=["int64", "float64"]).columns
    if len(num_cols) > 0:
        fig = px.histogram(df, x=num_cols[0])
        st.plotly_chart(fig)

else:
    st.info("Upload CSV to start.")
