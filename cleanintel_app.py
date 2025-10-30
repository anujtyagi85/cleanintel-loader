import streamlit as st
from supabase import create_client
import os
import pandas as pd
from datetime import date

st.set_page_config(page_title="CleanIntel • Smart Tender Assistant", page_icon="🧠", layout="centered")

# --- Connect to Supabase ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Session state ---
if "user" not in st.session_state:
    st.session_state["user"] = None
if "auth_mode" not in st.session_state:
    st.session_state["auth_mode"] = "login"

# --- AUTH UI ---
def auth_screen():
    st.title("🔑 CleanIntel Login / Signup")
    with st.form("auth_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Continue")

        if submit:
            if st.session_state["auth_mode"] == "login":
                user = supabase.auth.sign_in_with_password({"email": email, "password": password})
                if user.user:
                    st.session_state["user"] = user.user
                    st.experimental_rerun()
                else:
                    st.error("Invalid credentials. Try again or sign up.")
            else:
                user = supabase.auth.sign_up({"email": email, "password": password})
                if user.user:
                    st.success("✅ Signup successful! Verify your email, then log in.")
                else:
                    st.error("Error during signup. Try again.")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Create an account"):
            st.session_state["auth_mode"] = "signup"
            st.experimental_rerun()
    with col2:
        if st.button("Have an account? Login"):
            st.session_state["auth_mode"] = "login"
            st.experimental_rerun()

# --- LOGOUT ---
def logout():
    st.session_state["user"] = None
    supabase.auth.sign_out()
    st.experimental_rerun()

# --- USAGE HANDLING ---
def get_or_create_usage(user_id):
    record = supabase.table("user_usage").select("*").eq("user_id", user_id).execute()
    if not record.data:
        supabase.table("user_usage").insert({"user_id": user_id}).execute()
        return {"user_id": user_id, "searches_used": 0, "plan": "free", "last_reset": str(date.today())}
    return record.data[0]

def increment_usage(user_id):
    usage = get_or_create_usage(user_id)
    searches_used = usage["searches_used"] + 1
    supabase.table("user_usage").update({"searches_used": searches_used}).eq("user_id", user_id).execute()
    return searches_used

# --- MAIN APP ---
if not st.session_state["user"]:
    auth_screen()
    st.stop()

user_id = st.session_state["user"].id
usage = get_or_create_usage(user_id)
plan = usage["plan"]

# Plan limits
limit = 5 if plan == "free" else (500 if plan == "pro" else 999999)

st.sidebar.success(f"Logged in as {st.session_state['user'].email}")
st.sidebar.write(f"💳 Plan: **{plan.capitalize()}**")
st.sidebar.write(f"📊 Searches used: {usage['searches_used']}/{limit}")

if st.sidebar.button("🚪 Logout"):
    logout()

st.title("🧠 CleanIntel • Smart Tender Assistant")
st.write("Find **public cleaning tenders** faster and smarter — free for your first 5 searches each month.")

query = st.text_input("Describe what you're looking for", placeholder="e.g. school cleaning tenders closing next month")

if st.button("Search"):
    if usage["searches_used"] >= limit:
        st.error("⚠️ You’ve used all your free searches for this month.")
        st.link_button("💳 Upgrade to Pro (£20/month)", "https://buy.stripe.com/test_YOUR_PRO_PLAN_LINK_HERE")
        st.stop()

    new_count = increment_usage(user_id)
    st.success(f"Search recorded ✅ ({new_count}/{limit})")
    st.write(f"Searching tenders for: **{query}** ...")
    # Add your tender-fetching logic here
