import os
import streamlit as st
import pandas as pd
from supabase import create_client, Client
from dotenv import load_dotenv

# --- Load environment variables ---
load_dotenv()

SUPABASE_URL = st.secrets.get("SUPABASE_URL", os.getenv("SUPABASE_URL"))
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", os.getenv("SUPABASE_KEY"))

if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("❌ Missing Supabase credentials. Please add SUPABASE_URL and SUPABASE_KEY.")
    st.stop()

# --- Connect to Supabase ---
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    st.success("✅ Connected to Supabase successfully!")
except Exception as e:
    st.error(f"Failed to connect to Supabase: {e}")
    st.stop()

# --- Page setup ---
st.set_page_config(page_title="CleanIntel • Smart Tender Assistant", page_icon="🧠", layout="wide")

st.markdown("""
    <style>
    body { font-family: "Inter", sans-serif; }
    h1, h2, h3 { color: #333333; }
    .stButton>button {
        background-color: #ef8c00;
        color: white;
        border: none;
        padding: 0.5rem 1rem;
        border-radius: 8px;
    }
    .stButton>button:hover {
        background-color: #d97a00;
        color: white;
    }
    </style>
""", unsafe_allow_html=True)

# --- App Title ---
st.title("🧠 CleanIntel • Smart Tender Assistant")
st.write("Type how you think. Get tenders that matter.")

# --- Search form ---
query = st.text_input("Describe what you're looking for", 
                      placeholder="e.g. school cleaning tenders in UK under £2m closing next month")

col1, col2 = st.columns([1, 1])
with col1:
    search_btn = st.button("🔍 Search")
with col2:
    example_btn = st.button("✨ Try example")

if example_btn:
    query = "school cleaning tenders in UK under £2m closing next month"
    st.session_state["query"] = query
    st.experimental_rerun()

# --- Helper function ---
def load_tenders(keyword: str):
    try:
        response = supabase.table("tenders").select("*").ilike("title", f"%{keyword}%").execute()
        if not response.data:
            return pd.DataFrame()
        df = pd.DataFrame(response.data)
        if "deadline" in df.columns:
            df["deadline"] = pd.to_datetime(df["deadline"], errors="coerce", utc=True)
        return df
    except Exception as e:
        st.error(f"Error loading tenders: {e}")
        return pd.DataFrame()

# --- Search logic ---
if search_btn and query:
    with st.spinner("Searching tenders..."):
        df = load_tenders(query)
        if df.empty:
            st.warning("⚠️ No tenders matched that query. Try simplifying your prompt.")
        else:
            st.success(f"✅ Loaded {len(df)} matching tenders")
            st.dataframe(
                df[["country", "source", "title", "description", "value_gbp", "deadline"]]
                .sort_values("deadline", ascending=True)
                .reset_index(drop=True)
            )
else:
    st.info("💡 Enter a search term and click **Search** to get tender results.")

# --- Footer ---
st.markdown("""
---
© 2025 **CleanIntel**. Built for smarter public tenders.
""")
