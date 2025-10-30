import streamlit as st
from supabase import create_client
import os
from datetime import datetime
import requests

# --- Page setup ---
st.set_page_config(
    page_title="CleanIntel • Smart Tender Assistant",
    page_icon="🧠",
    layout="centered",
)

# --- Environment setup ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("Missing Supabase credentials. Please add SUPABASE_URL and SUPABASE_KEY.")
    st.stop()

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Authentication helpers ---
def get_user(email):
    result = supabase.table("user_usage").select("*").eq("email", email).execute().data
    return result[0] if result else None

def create_user(email, plan="Free"):
    data = {
        "email": email,
        "plan": plan,
        "searches_used": 0,
        "created_at": datetime.utcnow().isoformat(),
    }
    supabase.table("user_usage").insert(data).execute()
    return data

def increment_usage(email):
    user = get_user(email)
    if not user:
        return 0
    new_count = (user["searches_used"] or 0) + 1
    supabase.table("user_usage").update({"searches_used": new_count}).eq("email", email).execute()
    return new_count

# --- Authentication screen ---
def auth_screen():
    st.title("🔑 CleanIntel Login / Signup")

    email = st.text_input("Email")
    password = st.text_input("Password", type="password")

    if st.button("Continue"):
        if not email or not password:
            st.warning("Please enter both email and password.")
            st.stop()

        # Sign up or login
        try:
            user = get_user(email)
            if not user:
                create_user(email)
                st.success("Account created successfully! Please confirm your email (check inbox).")
            else:
                st.success(f"Welcome back, {email}!")
            st.session_state["user"] = email
            st.experimental_rerun()
        except Exception as e:
            st.error(f"Authentication failed: {e}")

    st.write("")
    st.button("Create an account", on_click=lambda: st.experimental_rerun())
    st.button("Have an account? Login", on_click=lambda: st.experimental_rerun())

# --- Main app (after login) ---
def app_main():
    email = st.session_state["user"]
    user = get_user(email)

    if not user:
        st.error("User not found. Please log in again.")
        st.session_state.pop("user", None)
        st.experimental_rerun()

    plan = user.get("plan", "Free")
    searches_used = user.get("searches_used", 0)
    limit = 5 if plan == "Free" else 100

    st.sidebar.success(f"Logged in as {email}")
    st.sidebar.write(f"🪙 Plan: {plan}")
    st.sidebar.write(f"📊 Searches used: {searches_used}/{limit}")
    if st.sidebar.button("🚪 Logout"):
        st.session_state.pop("user", None)
        st.experimental_rerun()

    st.title("🧠 CleanIntel • Smart Tender Assistant")
    st.write("Find **public cleaning tenders** faster and smarter — free for your first 5 searches each month.")

    query = st.text_input("Describe what you're looking for", placeholder="e.g. NHS cleaning tenders")
    if st.button("Search"):
        if searches_used >= limit:
            st.error("⚠️ You’ve used all your free searches for this month.")
            st.link_button("💳 Upgrade to Pro (£20/month)", "https://buy.stripe.com/test_YOUR_PRO_PLAN_LINK")
            st.stop()

        new_count = increment_usage(email)
        st.success(f"Search recorded ✅ ({new_count}/{limit})")
        st.write(f"Searching tenders for: **{query}** ...")

        # --- Fetch tenders from Supabase ---
        try:
            results = (
                supabase.table("tenders")
                .select("*")
                .ilike("title", f"%{query}%")
                .limit(25)
                .execute()
                .data
            )

            if not results:
                st.info("No tenders found matching your query.")
            else:
                for tender in results:
                    title = tender.get("title", "Untitled")
                    buyer = tender.get("buyer", "Unknown")
                    desc = tender.get("description", "")
                    value_low = tender.get("value_low", "—")
                    value_high = tender.get("value_high", "—")
                    close = tender.get("closing_date", "—")
                    url = tender.get("source_url", "#")

                    st.markdown(f"### [{title}]({url})")
                    st.write(desc or "No description provided.")
                    st.caption(
                        f"🏢 Buyer: {buyer}  |  💰 £{value_low} - £{value_high}  |  📅 Closing: {close}"
                    )
                    st.markdown("---")
        except Exception as e:
            st.error(f"Error loading tenders: {e}")

# --- Entry point ---
if "user" not in st.session_state:
    auth_screen()
else:
    app_main()
