import streamlit as st
import pandas as pd
import os
from supabase import create_client, Client
import streamlit_authenticator as stauth

st.set_page_config(page_title="CleanIntel • Smart Tender Assistant", layout="wide")

# env
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# -------------------------------
# AUTH
# -------------------------------
credentials = {
    "usernames": {
        "anujtyagi074@gmail.com": {
            "email": "anujtyagi074@gmail.com",
            "name": "Anuj",
            "password": stauth.Hasher(["cleanintel123"]).__call__()[0]
        }
    }
}

authenticator = stauth.Authenticate(
    credentials, "cleanintel_cookie", "abcdef", cookie_expiry_days=2
)

name, authentication_status, username = authenticator.login("Login", "main")

if authentication_status != True:
    st.warning("Please login first.")
    st.stop()

authenticator.logout("Logout", "sidebar")

user_email = username

# -------------------------------
# Header Content
# -------------------------------
st.markdown("## 🧠 CleanIntel • Smart Tender Assistant")
st.write("Find public cleaning tenders faster and smarter — free for your first 5 searches each month.")

# -------------------------------
# Filters + Form
# -------------------------------
search_term = st.text_input("Describe what you're looking for", "")

st.sidebar.subheader("Filters")

min_val = st.sidebar.number_input("Min Tender Value (GBP)", min_value=0, value=0)
max_val = st.sidebar.number_input("Max Tender Value (GBP)", min_value=0, value=0)

# if 0 → normalize to None
if min_val == 0:
    min_val = None
if max_val == 0:
    max_val = None

# -------------------------------
# Search Button
# -------------------------------
if st.button("Search") and search_term.strip() != "":
    
    # log
    supabase.rpc("record_search_activity", {"user_email": user_email}).execute()
    
    # MAIN RPC CALL
    response = supabase.rpc(
        "tender_keyword_search",
        {"search_term": search_term, "min_val": min_val, "max_val": max_val}
    ).execute()

    if response.data is None or len(response.data) == 0:
        st.info("No tenders matched. Try a broader term.")
    else:
        df = pd.DataFrame(response.data)
        st.success(f"Search completed — {len(df)} results found")
        st.dataframe(df)
