import streamlit as st
from supabase import create_client, Client
import pandas as pd
import os
from streamlit_supabase_auth import login_form

st.set_page_config(page_title="CleanIntel • Smart Tender Assistant", layout="wide")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ---------------- AUTH -----------------
user = login_form()
if not user:
    st.warning("Please login first.")
    st.stop()

user_email = user.email


# ---------------- HEADER -----------------
st.markdown("## 🧠 CleanIntel • Smart Tender Assistant")
st.write("Find public cleaning tenders faster and smarter — free for your first 5 searches each month.")

plan = st.session_state.get("plan", "free")
searches_used = st.session_state.get("searches_used", 0)

with st.sidebar:
    st.write(f"**Logged in as**: {user_email}")
    st.write(f"Plan: `{plan}`")
    st.write(f"Searches used: **{searches_used}/5**")

    if st.button("Logout"):
        st.session_state.clear()
        st.switch_page("pages/login.py")


# ---------------- SEARCH + FILTERS -----------------
search_term = st.text_input("Describe what you're looking for", "")

st.sidebar.subheader("Filters")

min_val = st.sidebar.number_input("Min Tender Value (GBP)", min_value=0, value=0)
max_val = st.sidebar.number_input("Max Tender Value (GBP)", min_value=0, value=0)

if min_val == 0:
    min_val = None
if max_val == 0:
    max_val = None


# ---------------- SEARCH ACTION -----------------
if st.button("Search") and search_term.strip() != "":

    # log usage
    supabase.rpc("record_search_activity", {"user_email": user_email}).execute()

    result = supabase.rpc(
        "tender_keyword_search",
        {
            "search_term": search_term,
            "min_value": min_val,
            "max_value": max_val
        }
    ).execute()

    if result.data is None or len(result.data) == 0:
        st.info("No tenders matched. Try a broader term.")
    else:
        df = pd.DataFrame(result.data)
        st.success(f"Search recorded ✅ ({searches_used+1}/5)")
        st.dataframe(df, use_container_width=True)
