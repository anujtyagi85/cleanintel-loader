import streamlit as st
from supabase import create_client, Client
import pandas as pd
import os

st.set_page_config(page_title="CleanIntel • Smart Tender Assistant", layout="wide")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

st.markdown("## 🧠 CleanIntel • Smart Tender Assistant")
st.write("Find public cleaning tenders faster and smarter — free for your first 5 searches each month.")

# auth session
session = st.session_state.get("user")
if not session:
    st.warning("Please login first.")
    st.stop()

user_email = session['user']['email']

plan = st.session_state.get("plan", "free")
searches_used = st.session_state.get("searches_used", 0)

st.sidebar.write(f"Logged in as\n### {user_email}")
st.sidebar.write(f"Plan: {plan}")
st.sidebar.write(f"Searches used: {searches_used}/5")

if st.sidebar.button("Logout"):
    st.session_state.clear()
    st.switch_page("pages/login.py")

search_term = st.text_input("Describe what you're looking for", "")

########## FILTERS ##########
st.sidebar.subheader("Filters")

min_val = st.sidebar.number_input("Min Tender Value (GBP)", min_value=0, value=0)
max_val = st.sidebar.number_input("Max Tender Value (GBP)", min_value=0, value=0)

# normalize 0 to None for RPC
if min_val == 0:
    min_val = None
if max_val == 0:
    max_val = None

###################################

if st.button("Search") and search_term.strip() != "":
    
    # record usage
    supabase.rpc("record_search_activity", {"user_email": user_email}).execute()

    result = supabase.rpc(
        "tender_keyword_search",
        {
            "search_term": search_term,
            "min_value": min_val,
            "max_value": max_val
        }
    ).execute()

    st.success(f"Search recorded ✅ ({searches_used+1}/5)")

    if result.data:
        df = pd.DataFrame(result.data)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No tenders matched. Try broader term.")
