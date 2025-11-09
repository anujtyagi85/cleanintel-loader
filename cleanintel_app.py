import os
import streamlit as st
from supabase import create_client

st.set_page_config(page_title="CleanIntel Data Viewer", layout="wide")

st.title("CleanIntel Data Viewer")
st.header("Search UK Government Tenders")

# env
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
supabase = create_client(url, key)

keyword = st.text_input("Search keyword (example: cleaning, solar, medical, school, waste)")

if keyword:
    response = (
        supabase.table("tenders")
        .select("value_normalized, sector, buyer, deadline, notice_url")
        .text_search("search_vector", keyword)
        .range(0,50)
        .execute()
    )

    results = response.data or []

    if len(results) == 0:
        st.warning("No records found.")
    else:
        st.success(f"Found {len(results)} records")
        st.write(results)
