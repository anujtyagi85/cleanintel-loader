import streamlit as st
from supabase import create_client
import pandas as pd
import os

st.set_page_config(page_title="CleanIntel • Smart Tender Assistant", page_icon="🧠", layout="centered")

# --- Connect to Supabase ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("❌ Missing Supabase credentials. Please add SUPABASE_URL and SUPABASE_KEY.")
    st.stop()

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
st.success("✅ Connected to Supabase successfully!")

# --- Homepage mode ---
st.title("🧠 CleanIntel")
st.subheader("Smart Tender Assistant")
st.markdown("Find **public cleaning tenders** faster and smarter — free for early users.")

if "search_mode" not in st.session_state:
    st.session_state["search_mode"] = False

# Homepage sections
if not st.session_state["search_mode"]:
    st.markdown("### 🚀 Start searching instantly")
    col1, col2 = st.columns([1,1])
    with col1:
        if st.button("🔍 Try it Free", use_container_width=True):
            st.session_state["search_mode"] = True
            st.experimental_rerun()
    with col2:
        st.link_button("💼 Login / Signup", "https://forms.gle/YOUR_FORM_LINK_HERE", use_container_width=True)

    st.divider()
    st.markdown("### 💸 Pricing Plans")
    st.markdown("""
    | Plan | Price | Features |
    |------|-------|-----------|
    | **Free** | £0 | 20 tender searches/month |
    | **Pro** | £10/mo | 500 searches + filters |
    | **Enterprise** | Custom | API access + support |
    """)

    st.divider()
    st.caption("© 2025 CleanIntel. Built for smarter public tenders.")
    st.stop()

# --- Tender Search Mode ---
st.text_input("Describe what you're looking for", key="query", placeholder="e.g. cleaning tenders closing next month")
if st.button("Search"):
    query = st.session_state["query"]
    st.write(f"Searching tenders for: **{query}** ...")
    # (You can plug your existing tender-loading logic here)
