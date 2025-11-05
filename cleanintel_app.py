import os
import pandas as pd
import streamlit as st
from supabase import create_client, Client
from streamlit_authenticator import Authenticate

st.set_page_config(page_title="CleanIntel • Smart Tender Assistant", layout="wide")

# ---- Supabase client ----
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("Supabase environment variables are missing. Please set SUPABASE_URL and SUPABASE_KEY.")
    st.stop()

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ---- Auth (streamlit-authenticator 0.3.x) ----
# If you want to change email, update the key below and the 'email' field to match exactly.
credentials = {
    "usernames": {
        "anuj.tyagi074@gmail.com": {  # <-- change this key and email together if needed
            "email": "anuj.tyagi074@gmail.com",
            "name": "Anuj Tyagi",
            # hashed for "cleanintel123"
            "password": "$2b$12$VyDmP7Z6wtogzbHaxkHE7ugjrvByB1e2RI/ThV7nZbKPqu.3SbZWW",
        }
    }
}

authenticator = Authenticate(
    credentials=credentials,
    cookie_name="cleanintelapp",
    key="abcdef1234567890abcdef",   # any random string is fine here
    cookie_expiry_days=30,
)

# IMPORTANT for v0.3.x: first arg is the LOCATION ('main' | 'sidebar' | 'unrendered')
name, authentication_status, username = authenticator.login("main")

if authentication_status is False:
    st.error("Incorrect email or password.")
    st.stop()

if authentication_status is None:
    st.info("Please log in to continue.")
    st.stop()

# ---- Logged-in UI ----
authenticator.logout("Logout", "sidebar")

st.markdown("## 🧠 CleanIntel • Smart Tender Assistant")
st.write("Find public cleaning tenders faster and smarter — free for your first 5 searches each month.")

search_term = st.text_input("Describe what you're looking for", "")

st.sidebar.subheader("Filters")
min_val = st.sidebar.number_input("Min Tender Value (GBP)", min_value=0, value=0)
max_val = st.sidebar.number_input("Max Tender Value (GBP)", min_value=0, value=0)

if st.button("Search") and search_term.strip():
    # normalize 0 → None for the RPC
    min_arg = None if min_val == 0 else min_val
    max_arg = None if max_val == 0 else max_val

    payload = {
        "search_term": search_term,
        "min_value": min_arg,
        "max_value": max_arg,
    }

    try:
        resp = supabase.rpc("tender_keyword_search", payload).execute()
    except Exception as e:
        st.error(f"Search failed: {e}")
        st.stop()

    if resp.data:
        df = pd.DataFrame(resp.data)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No tenders found for this search.")
