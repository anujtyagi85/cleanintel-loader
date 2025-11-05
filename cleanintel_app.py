import streamlit as st
import streamlit_authenticator as stauth
import pandas as pd
import requests
from supabase import create_client, Client
from dotenv import load_dotenv
import os

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

st.set_page_config(page_title="CleanIntel Loader", layout="wide")

# -------- AUTH SECTION ----------
hashed_passwords = [
    "$2b$12$VyDmP7Z6wtogzbHaxkHE7ugjrvByB1e2RI/ThV7nZbKPqu.3SbZWW"
]

credentials = {
    "usernames":{
        "anuj.tyagi074@gmail.com":{
            "email":"anuj.tyagi074@gmail.com",
            "name":"Anuj",
            "password":hashed_passwords[0]
        }
    }
}

authenticator = stauth.Authenticate(
    credentials,
    "cleanintel_cookie",
    "cleanintel_signature",
    cookie_expiry_days=1
)

name, authentication_status, username = authenticator.login("Login", "main")

if authentication_status == False:
    st.error("Incorrect username/password")

if authentication_status == None:
    st.warning("Please login first.")

if authentication_status:
    authenticator.logout("Logout", "sidebar")
    st.title("CleanIntel Loader")

    st.subheader("Upload CSV")
    uploaded_file = st.file_uploader("Choose CSV", type=["csv"])

    if uploaded_file is not None:
        df = pd.read_csv(uploaded_file)
        st.success("File loaded successfully")
        st.dataframe(df)

        if st.button("Upload to Supabase"):
            data = df.to_dict(orient="records")
            resp = supabase.table("cleanintel_raw").insert(data).execute()
            st.success("Uploaded to Supabase successfully!")
