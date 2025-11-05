import streamlit as st
from supabase import create_client, Client
import pandas as pd
import os
from streamlit_auth_ui.widgets import login_form

st.set_page_config(page_title="CleanIntel • Smart Tender Assistant", layout="wide")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

st.markdown("## 🧠 CleanIntel • Smart Tender Assistant")
st.write("Find public cleaning tenders faster and smarter — free for your first 5 searches each month.")

### LOGIN
session = login_form(supabase)
if session is None:
    st.warning("Please login first.")
    st.stop()

user_email = session.user.email

### plan + usage logic
user_usage = supabase.table("user_usage").select("*").eq("user_email", user_email).single().execute()
if user_usage.data is None:
    supabase.table("user_usage").insert({"user_email": user_email, "searches_used": 0, "plan": "free"}).execute()
    searches_used = 0
    plan = "free"
else:
    searches_used = user_usage.data["searches_used"]
    plan = user_usage.data["plan"]

st.sidebar.write(f"Logged in as **{user_email}**")
st.sidebar.write(f"Plan: {plan}")
st.sidebar.write(f"Searches used: {searches_used}/5")

if plan == "free" and searches_used >= 5:
    st.error("You reached your monthly quota. Upgrade plan to continue.")
    st.stop()

### Filters
st.sidebar.subheader("Filters")
min_val = st.sidebar.number_input("Min Tender Value (GBP)", min_value=0, value=0)
max_val = st.sidebar.number_input("Max Tender Value (GBP)", min_value=0, value=0)
if max_val == 0: max_val = None
if min_val == 0: min_val = None

### search input
search_term = st.text_input("Describe what you're looking for", "")

if st.button("Search") and search_term.strip() != "":
    supabase.rpc("record_search_activity", {"user_email": user_email}).execute()

    result = supabase.rpc(
        "tender_keyword_search",
        {"search_term": search_term}
    ).execute()

    df = pd.DataFrame(result.data)

    # apply filters locally
    if min_val is not None:
        df = df[df["value_gbp"] >= min_val]
    if max_val is not None:
        df = df[df["value_gbp"] <= max_val]

    st.success(f"Search recorded ✅ ({searches_used+1}/5)")
    st.dataframe(df)
