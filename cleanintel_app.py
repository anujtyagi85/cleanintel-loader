import os
import streamlit as st
from supabase import create_client
import pandas as pd

st.set_page_config(page_title="CleanIntel Data Viewer", layout="wide")

st.title("CleanIntel Data Viewer")

# ===================== SUPABASE CONNECT =======================
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ===================== SEARCH UI ===============================

st.header("Search UK Government Tenders")
keyword = st.text_input("Search keyword (example: cleaning, solar, medical, school, waste)")

if keyword:

    query = supabase.table("tenders") \
        .select("buyer ->> name, value_normalized, sector, deadline, notice_url") \
        .limit(50)

    query = query.text_search("search_vector", keyword)

    response = query.execute()

    results = response.data or []

    st.success(f"Found {len(results)} results")

    if len(results) > 0:
        df = pd.DataFrame(results)

        # reorder columns
        desired_order = ["buyer ->> name", "value_normalized", "sector", "deadline", "notice_url"]
        df = df[desired_order]

        # rename nicer
        df.columns = ["buyer", "value", "sector", "deadline", "notice_url"]

        st.dataframe(df, use_container_width=True)
