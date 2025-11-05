import streamlit as st
import pandas as pd
import numpy as np
import os
from supabase import create_client, Client
from streamlit_authenticator import Authenticate

st.set_page_config(page_title="CleanIntel Loader", page_icon="🧼")

# -------- AUTH  --------
hashed_passwords = {
    "anuj.tyagi074@gmail.com": "$2b$12$VyDmP7Z6wtogzbHaxkHE7ugjrvByB1e2RI/ThV7nZbKPqu.3SbZWW"
}

authenticator = Authenticate(
    {"anuj.tyagi074@gmail.com": {"name": "Anuj Tyagi", "password": hashed_passwords["anuj.tyagi074@gmail.com"]}},
    cookie_name="cleanintel_cookie",
    key="abcdef",
    cookie_expiry_days=30
)

name, authentication_status, username = authenticator.login("Login", "main")

if authentication_status == False:
    st.error("Username or password is incorrect")
elif authentication_status is None:
    st.warning("Please enter username and password")
elif authentication_status:
    st.success(f"Welcome {name}!")
    authenticator.logout("Logout", "sidebar")

    # -------- MAIN APP --------
    st.title("CleanIntel CSV Loader")

    st.write("Upload CSV to process it")

    uploaded_file = st.file_uploader("Upload CSV", type=["csv"])

    if uploaded_file:
        df = pd.read_csv(uploaded_file)
        st.dataframe(df)
