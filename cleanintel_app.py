import os
import streamlit as st
from supabase import create_client
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="CleanIntel – UK Tender Intelligence", layout="wide")

# Connect
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
supabase = create_client(url, key)

TABLE = "tenders"

def fetch_rows_by_title(kw: str):
    if not kw:
        return (
            supabase.table(TABLE)
            .select("title,buyer,value_gbp,status,deadline")
            .limit(200)
            .execute()
            .data
        )

    return (
        supabase.table(TABLE)
        .select("title,buyer,value_gbp,status,deadline")
        .ilike("title", f"%{kw}%")
        .limit(200)
        .execute()
        .data
    )


def fetch_rows_by_buyer_name(kw: str):
    return (
        supabase.table(TABLE)
        .select("title,buyer,value_gbp,status,deadline")
        .ilike("buyer::text", f"%{kw}%")
        .limit(200)
        .execute()
        .data
    )


st.title("CleanIntel – UK Tender Intelligence")
st.caption("Fuzzy search in title or buyer + scoring idea coming next (v1 heuristic).")

st.subheader("Search UK Government Tenders")

keyword = st.text_input("Keyword (fuzzy match in title, fallback to buyer)", placeholder="e.g., cleaning, school, waste, solar")

if keyword:

    # 1) search in title first
    results = fetch_rows_by_title(keyword)

    # 2) if none found -> fallback to buyer json text search
    if len(results) == 0:
        results = fetch_rows_by_buyer_name(keyword)

    if len(results) == 0:
        st.warning("No tenders found matching this.")
    else:
        st.success(f"Found {len(results)} tenders")

        df = pd.DataFrame(results)

        # buyer is json -> extract name safely
        if "buyer" in df.columns:
            df["buyer_name"] = df["buyer"].apply(lambda v: v.get("name") if isinstance(v, dict) else None)
            df = df.drop(columns=["buyer"])
            df = df.rename(columns={"buyer_name": "buyer"})

        # reorder
        desired = ["title", "buyer", "value_gbp", "status", "deadline"]
        df = df[desired]

        st.dataframe(df, use_container_width=True)
