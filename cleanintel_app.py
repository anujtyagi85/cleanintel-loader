import streamlit as st
from supabase import create_client
import os
import pandas as pd
from datetime import date

st.set_page_config(
    page_title="CleanIntel • Smart Tender Assistant",
    page_icon="🧠",
    layout="centered"
)

# --- Supabase connection ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("❌ Missing Supabase credentials. Please set SUPABASE_URL and SUPABASE_KEY.")
    st.stop()

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Session state init ---
if "user" not in st.session_state:
    st.session_state["user"] = None

# --- AUTH SCREEN ---
def auth_screen():
    st.title("🔑 CleanIntel Login / Signup")

    tabs = st.tabs(["Login", "Create Account"])

    # LOGIN TAB
    with tabs[0]:
        with st.form("login_form"):
            email = st.text_input("Email", key="login_email")
            password = st.text_input("Password", type="password", key="login_password")
            submit = st.form_submit_button("Login")

            if submit:
                try:
                    user = supabase.auth.sign_in_with_password({"email": email, "password": password})
                    if user.user:
                        st.session_state["user"] = user.user
                        st.rerun()
                    else:
                        st.error("Invalid credentials. Try again.")
                except Exception as e:
                    st.error(f"⚠️ {e}")

    # SIGNUP TAB
    with tabs[1]:
        with st.form("signup_form"):
            email = st.text_input("Email", key="signup_email")
            password = st.text_input("Password", type="password", key="signup_password")
            submit = st.form_submit_button("Create Account")

            if submit:
                try:
                    user = supabase.auth.sign_up({"email": email, "password": password})
                    if user.user:
                        st.success("✅ Account created! Please verify your email before logging in.")
                    else:
                        st.error("Signup failed. Try again.")
                except Exception as e:
                    st.error(f"⚠️ {e}")

# --- LOGOUT FUNCTION ---
def logout():
    st.session_state["user"] = None
    try:
        supabase.auth.sign_out()
    except Exception:
        pass
    st.rerun()

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

# Limits by plan
limit = 5 if plan == "free" else (500 if plan == "pro" else 999999)

# --- SIDEBAR ---
st.sidebar.success(f"Logged in as {st.session_state['user'].email}")
st.sidebar.write(f"💳 Plan: **{plan.capitalize()}**")
st.sidebar.write(f"📊 Searches used: {usage['searches_used']}/{limit}")

if st.sidebar.button("🚪 Logout"):
    logout()

# --- MAIN INTERFACE ---
st.title("🧠 CleanIntel • Smart Tender Assistant")
st.write("Find **public cleaning tenders** faster and smarter — free for your first 5 searches each month.")

query = st.text_input(
    "Describe what you're looking for",
    placeholder="e.g. school cleaning tenders closing next month"
)

if st.button("Search"):
    if usage["searches_used"] >= limit:
        st.error("⚠️ You’ve used all your free searches for this month.")
        st.link_button("💳 Upgrade to Pro (£20/month)", "https://buy.stripe.com/test_YOUR_PRO_PLAN_LINK_HERE")
        st.stop()

    new_count = increment_usage(user_id)
    st.success(f"Search recorded ✅ ({new_count}/{limit})")
    st.write(f"Searching tenders for: **{query}** ...")
    st.info("🔍 (Mock result placeholder — real tender data integration coming soon.)")

# --- FOOTER ---
st.markdown("---")
st.caption("© 2025 CleanIntel. Built for smarter public tenders.")
