import streamlit as st
from supabase import create_client
import os
import pandas as pd

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
                    st.success(f"Welcome back, {email}!")
                    st.experimental_rerun()
                else:
                    st.error("Invalid credentials. Try again or sign up.")
            else:
                user = supabase.auth.sign_up({"email": email, "password": password})
                if user.user:
                    st.success("✅ Signup successful! Please verify your email, then log in.")
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
    st.success("Logged out!")
    st.experimental_rerun()

# --- MAIN APP ---
if not st.session_state["user"]:
    auth_screen()
    st.stop()

st.sidebar.success(f"Logged in as {st.session_state['user'].email}")
if st.sidebar.button("🚪 Logout"):
    logout()

st.title("🧠 CleanIntel • Smart Tender Assistant")
st.write("Find **public cleaning tenders** faster and smarter.")

query = st.text_input("Describe what you're looking for", placeholder="e.g. school cleaning tenders closing next month")
if st.button("Search"):
    st.write(f"Searching tenders for: **{query}** ... (sample results below)")
