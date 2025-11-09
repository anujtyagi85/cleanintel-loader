import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime, timezone

import os

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

st.set_page_config(page_title="CleanIntel – UK Tender Intelligence", layout="wide")

st.title("CleanIntel – UK Tender Intelligence")
st.caption("Fuzzy search in title, with fallback to buyer name (JSON).")

keyword = st.text_input("Keyword (fuzzy match in title, fallback to buyer)", placeholder="e.g., cleaning, school, waste, solar")

# --- buyer normalisation ---
def extract_buyer_name(obj):
    if isinstance(obj, dict):
        if "name" in obj and obj["name"]:
            return obj["name"]
        if "contactPoint" in obj and isinstance(obj["contactPoint"], dict):
            return obj["contactPoint"].get("name")
        if "organization" in obj and isinstance(obj["organization"], dict):
            return obj["organization"].get("name")
    return None


if keyword:

    # Try title first
    query = (
        supabase.table("tenders")
        .select("title,buyer,value_gbp,status,deadline")
        .ilike("title", f"%{keyword}%")
        .limit(200)
    )

    response = query.execute()
    rows = response.data

    # if no rows → fallback to buyer object json search
    if not rows or len(rows) == 0:
        query2 = (
            supabase.table("tenders")
            .select("title,buyer,value_gbp,status,deadline")
            .ilike("buyer::text", f"%{keyword}%")
            .limit(200)
        )
        response = query2.execute()
        rows = response.data

    if rows and len(rows) > 0:
        df = pd.DataFrame(rows)

        # apply buyer normalization
        df["buyer_name"] = df["buyer"].apply(extract_buyer_name)

        # reorder columns
        df = df[["title","buyer_name","value_gbp","status","deadline"]]

        st.success(f"Found {len(df)} tenders")
        st.dataframe(df, use_container_width=True)
    else:
        st.warning("No tenders found.")
