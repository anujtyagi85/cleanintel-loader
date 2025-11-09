import os
import streamlit as st
from supabase import create_client
import pandas as pd

st.set_page_config(page_title="CleanIntel Data Viewer", layout="wide")

st.title("CleanIntel – UK Tender Intelligence")

# ===================== SUPABASE CONNECT =======================
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ===================== SEARCH UI ===============================
st.subheader("Search UK Government Tenders")

keyword = st.text_input("Keyword (try: cleaning, school, waste, solar, carpets, catering etc)")

if keyword:

    query = supabase.table("tenders") \
        .select("title, buyer, value_gbp, status, deadline") \
        .limit(50)

    query = query.text_search("search_vector", keyword)

    response = query.execute()

    results = response.data or []

    st.success(f"Found {len(results)} tenders")

    if len(results) > 0:
        df = pd.DataFrame(results)

        desired_order = ["title", "buyer", "value_gbp", "status", "deadline"]
        df = df[desired_order]

        st.dataframe(df, use_container_width=True)
