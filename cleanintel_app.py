import os
from datetime import datetime, timezone

import pandas as pd
import streamlit as st
from supabase import create_client

# ---------- Page ----------
st.set_page_config(page_title="CleanIntel – UK Tender Intelligence", layout="wide")
st.title("CleanIntel – UK Tender Intelligence")
st.caption("Fuzzy search in title, with fallback to buyer name (JSON) + simple scoring (time + value).")

# ---------- Supabase ----------
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("Supabase credentials are missing. Set SUPABASE_URL and SUPABASE_KEY in app secrets.")
    st.stop()

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

TABLE = "public.tenders"

# ---------- UI ----------
keyword = st.text_input(
    "Keyword (fuzzy match in title, fallback to buyer)",
    placeholder="e.g., cleaning, school, waste, solar",
    value="",
)

# ---------- Helpers ----------
def fetch_rows_by_title(kw: str):
    """
    SELECT title, buyer->>name AS buyer_name, value_gbp, status, deadline
    WHERE title ILIKE %kw%
    LIMIT 200
    """
    if not kw:
        return (
            supabase.table(TABLE)
            .select("title,buyer_name:buyer->>name,value_gbp,status,deadline")
            .limit(200)
            .execute()
            .data
        )

    return (
        supabase.table(TABLE)
        .select("title,buyer_name:buyer->>name,value_gbp,status,deadline")
        .ilike("title", f"%{kw}%")
        .limit(200)
        .execute()
        .data
    )


def fetch_rows_by_buyer_name(kw: str):
    """
    Fallback: search in buyer->>name
    """
    return (
        supabase.table(TABLE)
        .select("title,buyer_name:buyer->>name,value_gbp,status,deadline")
        .ilike("buyer->>name", f"%{kw}%")
        .limit(200)
        .execute()
        .data
    )


def score_and_sort(df: pd.DataFrame) -> pd.DataFrame:
    """Compute days_left, score, and sort."""
    # Normalize types
    # deadline may be null or text; coerce to datetime (UTC)
    df["deadline"] = pd.to_datetime(df["deadline"], errors="coerce", utc=True)

    # value might be None/str; coerce to numeric
    df["value_gbp"] = pd.to_numeric(df["value_gbp"], errors="coerce")

    now_utc = datetime.now(timezone.utc)
    # days_left can be NaN; fill with -1 so they sort to bottom
    df["days_left"] = (df["deadline"] - now_utc).dt.days
    df["days_left"] = df["days_left"].fillna(-1)

    # simple score:
    # +1 if days_left >= 21
    # +1 if value_gbp >= 250,000
    df["time_score"] = (df["days_left"] >= 21).astype(int)
    df["value_score"] = (df["value_gbp"] >= 250_000).astype(int)
    df["score"] = df["time_score"] + df["value_score"]

    # Sort
    df = df.sort_values(
        by=["score", "value_gbp", "days_left"],
        ascending=[False, False, False],
        kind="mergesort",
    )

    # Reorder and pretty
    df = df.rename(columns={"buyer_name": "buyer"})
    show_cols = ["title", "buyer", "value_gbp", "status", "deadline", "days_left", "score"]
    existing = [c for c in show_cols if c in df.columns]
    return df[existing]


# ---------- Query & Render ----------
if keyword is not None:
    try:
        rows = fetch_rows_by_title(keyword.strip())
        if not rows:
            rows = fetch_rows_by_buyer_name(keyword.strip())

        df = pd.DataFrame(rows)

        st.success(f"Found {len(df)} tenders")

        if df.empty:
            st.info("No tenders matched your query.")
        else:
            df_view = score_and_sort(df)
            st.dataframe(
                df_view,
                use_container_width=True,
                hide_index=True,
            )

            with st.expander("How scoring works"):
                st.markdown(
                    """
- **+1** if `days_left ≥ 21` (more runway → higher chance to prepare a good bid)
- **+1** if `value_gbp ≥ 250,000` (larger contracts prioritized)
- Sorted by **score**, then **value**, then **days_left**.
"""
                )

    except Exception as e:
        st.error("Query failed. Check logs (Manage app) for details.")
