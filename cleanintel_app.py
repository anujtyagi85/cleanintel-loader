import streamlit as st
from supabase import create_client
import pandas as pd

st.set_page_config(page_title="CleanIntel Data Viewer", layout="wide")

# ======== connect supabase =========
SUPABASE_URL = "https://myohjatisjbalthdbwku.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im15b2hqYXRpc2piYWx0aGRid2t1Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2MDgzODg4MCwiZXhwIjoyMDc2NDE0ODgwfQ.f5dSb2e7SqKc3eZBYggENnVFwpovEaAt5b95xg_68gc"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

st.title("CleanIntel Data Viewer")
st.header("Search UK Government Tenders")

keyword = st.text_input("Search keyword (example: cleaning, solar, medical, school, waste)")

if keyword:
    response = (
        supabase.table("tenders")
        .select("buyer ->> name, value_normalized, deadline, notice_url")
        .text_search("search_vector", keyword)
        .limit(50)
        .execute()
    )

    results = response.data or []
    st.success(f"Found {len(results)} results")

    if results:
        df = pd.DataFrame(results)
        df = df.rename(columns={
            "buyer ->> name": "buyer"
        })
        df = df[["buyer", "value_normalized", "deadline", "notice_url"]]

        st.dataframe(df)
