import os
import pandas as pd
import streamlit as st
from supabase import create_client

st.set_page_config(page_title="CleanIntel Data Viewer", layout="wide")

# SUPABASE init
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
supabase = create_client(url, key)

st.title("CleanIntel Data Viewer")

st.header("Search UK Government Tenders")
keyword = st.text_input("Search keyword (example: cleaning, solar, medical, school, waste)")

if keyword:
    response = (
        supabase.table("tenders")
        .select("buyer,value_normalized,sector,deadline,notice_url")
        .text_search("search_vector", keyword)
        .execute()
    )

    results = response.data or []

    if len(results) == 0:
        st.warning("No results found")
    else:
        df = pd.DataFrame(results)

        # cleanup deadline
        df["deadline"] = pd.to_datetime(df["deadline"], errors="coerce")

        # sanitize numeric values
        def clean_value(v):
            try:
                if isinstance(v, dict):
                    return v.get("amount")
                return float(v)
            except:
                return None

        df["value_normalized"] = df["value_normalized"].apply(clean_value)

        # final column order
        df = df[["buyer", "value_normalized", "sector", "deadline", "notice_url"]]

        # sort earliest deadline first
        df = df.sort_values("deadline", ascending=True)

        # clickable URLs
        def make_clickable(url):
            if url and url != "None":
                return f"[OPEN]({url})"
            return ""

        df["notice_url"] = df["notice_url"].apply(make_clickable)

        st.success(f"Found {len(df)} results")
        st.write(df.to_markdown(), unsafe_allow_html=True)
