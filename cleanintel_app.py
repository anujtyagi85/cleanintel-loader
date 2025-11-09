import streamlit as st
from supabase import create_client
import os
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="CleanIntel – UK Tender Intelligence", page_icon="🧽", layout="wide")

# --- Supabase ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

st.title("CleanIntel – UK Tender Intelligence")

st.write("Fuzzy search in title, with fallback to buyer (JSON).")

keyword = st.text_input("Keyword (fuzzy match in title, fallback to buyer)")

if keyword:
    try:
        query = (
            supabase.table("tenders")
            .select("title, buyer, value_gbp, status, deadline")
            .or_(f"title.ilike.%{keyword}%,buyer::text.ilike.%{keyword}%")   # <-- FIX HERE
            .limit(200)
        )

        response = query.execute()
        rows = response.data

        if not rows:
            st.warning("No tenders found.")
        else:
            df = pd.DataFrame(rows)

            # TEMP BUYER NORMALISATION
            df["buyer_name"] = df["buyer"].astype(str).str.replace('"', '', regex=False).str.strip()

            df = df[["title", "buyer_name", "value_gbp", "status", "deadline"]]

            st.success(f"Found {len(df)} tenders")
            st.dataframe(df, use_container_width=True)

    except Exception as e:
        st.error(f"Query failed: {str(e)}")
