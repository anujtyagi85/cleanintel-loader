import os
import streamlit as st
from supabase import create_client
from streamlit_authenticator import Authenticate

st.set_page_config(page_title="CleanIntel Loader", layout="wide")

# ================= AUTH =================

hashed_password = "$2b$12$9Yubm2F6wtogzbahxKK7ugjxBYyBle2Rl/7hVn7h2bKPqu.3SbZWf"   # cleanintel123

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
    cookie_name="cleanintel_cookie_v2",   # <- new cookie name
    key="cleanintelkey_new987",           # <- new random key
    cookie_expiry_days=30
)
name, authentication_status, username = authenticator.login("Login")

if authentication_status is False:
    st.error("Incorrect username or password")

if authentication_status is None:
    st.warning("Please enter your username and password")

# ================= APP ===================

if authentication_status:
    authenticator.logout("Logout")
    st.title("CleanIntel Data Loader")
    st.success(f"Logged in as: {username}")

    # connect supabase
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    supabase = create_client(url, key)

    st.header("Search UK Government Tenders")
    keyword = st.text_input("Search keyword (example: cleaning, solar, medical, school, waste)")

    if keyword:
        response = supabase.table("tenders").select(
            "notice_id,status,buyer,value_normalized,deadline,notice_url"
        ).text_search(
            column="search_vector",
            query=keyword
        ).limit(50).execute()

        results = response.data or []
        st.write(results)
