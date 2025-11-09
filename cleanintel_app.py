import os
import streamlit as st
from supabase import create_client
from streamlit_authenticator import Authenticate

st.set_page_config(page_title="CleanIntel Loader", layout="wide")

# ---------------- AUTH ----------------

hashed_password = "$2b$12$VyDmP7Z6wtogzbHaxkHE7ugjrvByB1e2RI/ThV7nZbKPqu.3SbZWW"  # cleanintel123

credentials = {
    "anugroup": {
        "name": "Anuj Tyagi",
        "password": hashed_password
    }
}

authenticator = Authenticate(
    credentials,
    cookie_name="cleanintel_cookie",
    key="abcdcef",
    cookie_expiry_days=30
)

name, authentication_status, username = authenticator.login("Login")

if authentication_status == False:
    st.error("Incorrect username or password")

if authentication_status == None:
    st.warning("Please enter your username and password")

# ---------------- APP ----------------

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
        response = supabase.table("tenders") \
            .select("notice_id,status,buyer,value_normalized,deadline,notice_url") \
            .text_search("search_vector", keyword) \
            .limit(50) \
            .execute()

        results = response.data or []

        st.write(f"Results: {len(results)} tenders found")

        for row in results:
            st.subheader(row.get("notice_id","N/A"))
            st.write("Status:", row.get("status"))
            st.write("Buyer:", row.get("buyer"))
            st.write("Value:", row.get("value_normalized"))
            st.write("Deadline:", row.get("deadline"))
            st.write("URL:", row.get("notice_url"))
            st.write("---")
