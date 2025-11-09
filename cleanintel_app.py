import os
import streamlit as st
from supabase import create_client

st.set_page_config(page_title="CleanIntel Loader", layout="wide")

st.title("CleanIntel Data Viewer")

# connect supabase
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
supabase = create_client(url, key)

st.header("Search UK Government Tenders")

keyword = st.text_input("Search keyword (example: cleaning, solar, medical, school, waste)")

if keyword:

    response = (
        supabase.table("tenders")
        .select("value_normalized, sector, buyer, deadline")
        .text_search("search_vector", keyword)
        .limit(50)
        .execute()
    )

    results = response.data or []

    if len(results) == 0:
        st.warning("No tenders found for that keyword.")
    else:
        st.success(f"Showing {len(results)} tenders found")
        st.dataframe(results)
