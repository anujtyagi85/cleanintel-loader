import os
import streamlit as st
from supabase import create_client
from streamlit_authenticator import Authenticate

st.set_page_config(page_title="CleanIntel Loader", layout="wide")

# ----------------------- AUTH -----------------------

hashed_password = "$2b$12$VyDmP7Z6wtogzbHaxkHE7ugjrvByB1e2RI/ThV7nZbKPqu.3SbZWW"   # cleanintel123

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
    key="abcdce",
    cookie_expiry_days=30
)

name, authentication_status, username = authenticator.login("Login")

if authentication_status == False:
    st.error("Incorrect username or password")

if authentication_status is None:
    st.warning("Please enter your username and password")

# ----------------------- APP ------------------------

if authentication_status:

    authenticator.logout("Logout")
    st.title("CleanIntel Data Loader")

    st.success(f"Logged in as: {username}")

    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")

    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

    st.header("Search UK Government Tenders")

    keyword = st.text_input("Search keyword (example: cleaning, solar, medical, school, waste)")

    if keyword:
response = supabase.table("tenders").select(
    "notice_id,status,buyer,value_normalized,deadline,notice_url"
).text_search(
    column="search_vector",
    query=keyword

        results = response.data or []
        
        if len(results) == 0:
            st.warning("No tenders found for this keyword.")
        else:
            st.write(f"Found {len(results)} tenders:")
            st.dataframe(results, use_container_width=True)
