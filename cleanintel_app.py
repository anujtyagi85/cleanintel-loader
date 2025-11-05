import streamlit as st
from supabase import create_client, Client
import pandas as pd
import os
from streamlit_authenticator import Authenticate


st.set_page_config(page_title="CleanIntel • Smart Tender Assistant", layout="wide")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

### AUTH ###

credentials = {
    "usernames": {
        "anuj.tyagi074@gmail.com": {
            "email": "anuj.tyagi074@gmail.com",
            "name": "Anuj Tyagi",
            "password": "$2b$12$VyDmP7Z6wtogzbHaxkHE7ugjrvByB1e2RI/ThV7nZbKPqu.3SbZWW"
        }
    }
}

authenticator = Authenticate(
    credentials,
    "cleanintelapp",
    "abcdef1234567890abcdef",
    cookie_expiry_days=30
)

name, authentication_status, username = authenticator.login("Login", "main")

if authentication_status == False:
    st.error("Incorrect email or password")

if authentication_status is None:
    st.warning("Please login first.")

if authentication_status:

    authenticator.logout("Logout", "sidebar")

    st.markdown("## 🧠 CleanIntel • Smart Tender Assistant")
    st.write("Find public cleaning tenders faster and smarter — free for your first 5 searches each month.")

    search_term = st.text_input("Describe what you're looking for", "")

    st.sidebar.subheader("Filters")

    min_val = st.sidebar.number_input("Min Tender Value (GBP)", min_value=0, value=0)
    max_val = st.sidebar.number_input("Max Tender Value (GBP)", min_value=0, value=0)

    if st.button("Search") and search_term.strip() != "":
        
        if min_val == 0:
            min_val = None
        if max_val == 0:
            max_val = None

        rpc_payload = {
            "search_term": search_term,
            "min_value": min_val,
            "max_value": max_val
        }

        result = supabase.rpc("tender_keyword_search", rpc_payload).execute()

        if result.data:
            df = pd.DataFrame(result.data)
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No tenders found matching this search.")
