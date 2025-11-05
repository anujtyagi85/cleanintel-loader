import streamlit as st
import pandas as pd
import os
from streamlit_authenticator import Authenticate

st.set_page_config(page_title="CleanIntel Loader", layout="wide")

# AUTH SECTION ----------------------------
hashed_password = "$2b$12$VyDmP7Z6wtogzbHaxkHE7ugjrvByB1e2RI/ThV7nZbKPqu.3SbZWW"

credentials = {
    "usernames": {
        "anuj.tyagi074@gmail.com": {
            "name": "Anuj Tyagi",
            "password": hashed_password
        }
    }
}

authenticator = Authenticate(
    credentials,
    cookie_name="cleanintel_cookie",
    key="abcdcf",
    cookie_expiry_days=30
)

name, authentication_status, username = authenticator.login("Login")

if authentication_status == False:
    st.error("Username / Password is incorrect")

if authentication_status == None:
    st.warning("Please Login first.")

if authentication_status:
    authenticator.logout("Logout")
    st.title("CleanIntel Data Loader")

    st.write("✅ Logged in as:", username)

    # MAIN UI BODY (blank for now - we will build step 2 after login works)
    st.write("Upload CSV and push to Supabase will come next step.")
