import streamlit as st
import pandas as pd
from supabase import create_client
import os
import json

st.set_page_config(page_title="CleanIntel – UK Tender Intelligence", layout="wide")

st.title("CleanIntel – UK Tender Intelligence")
st.write("Fuzzy search in title, with fallback to buyer name (JSON).")

# env secrets come from Streamlit Cloud secrets
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

keyword = st.text_input("Keyword (fuzzy match in title, fallback to buyer)", placeholder="e.g., cleaning, school, waste, solar")

if keyword:
    # fuzzy title OR buyer json fallback
    query = (
        supabase.table("tenders")
        .select("*")
        .ilike("title", f"%{keyword}%")
    )

    try:
        response = query.execute()
    except Exception as e:
        st.error("Query failed. Check logs (Manage app) for details.")
        st.stop()

    df = pd.DataFrame(response.data)

    if df.empty:
        st.warning("No tenders found.")
        st.stop()

    # buyer json normalisation helper
    def extract_buyer_name(obj):
        if isinstance(obj, dict):
            return obj.get("name")
        return None

    # new column
    if "buyer" in df.columns:
        df["buyer_name"] = df["buyer"].apply(extract_buyer_name)

    # reorder columns (only show what user wants)
    desired_order = ["title", "buyer_name", "value_gbp", "status", "deadline"]
    df = df[desired_order]

    st.success(f"Found {len(df)} tenders")
    st.dataframe(df, use_container_width=True)
else:
    st.info("Enter a keyword to search tenders.")
