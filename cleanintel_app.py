import streamlit as st
from supabase import create_client
import os
import pandas as pd

st.set_page_config(page_title="CleanIntel – UK Tender Intelligence", page_icon="🧽", layout="wide")

# --- Supabase ENV ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

st.title("CleanIntel – UK Tender Intelligence")
st.write("Fuzzy search in title, fallback to buyer (JSON stored).")

keyword = st.text_input("Keyword (e.g., cleaning, school, waste, solar)")

if keyword:
    try:
        query = (
            supabase.table("tenders")
            .select("title, buyer, value_gbp, status, deadline")
            .or_(f"title.ilike.%{keyword}%,buyer::text.ilike.%{keyword}%")
            .limit(200)
        )

        response = query.execute()
        rows = response.data

        if not rows:
            st.warning("No tenders found.")
        else:
            df = pd.DataFrame(rows)

            # buyer JSON → readable string
            df["buyer_name"] = df["buyer"].astype(str).str.replace('"', '', regex=False).str.strip()

            df = df[["title", "buyer_name", "value_gbp", "status", "deadline"]]

            st.success(f"Found {len(df)} tenders")
            st.dataframe(df, use_container_width=True)

    except Exception as e:
        st.error(f"Query failed: {str(e)}")

else:
    st.info("Search tenders above to begin.")
