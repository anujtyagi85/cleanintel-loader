import os
from datetime import datetime, timezone
import pandas as pd
import streamlit as st
from supabase import create_client

st.set_page_config(page_title="CleanIntel – UK Tender Intelligence", layout="wide")
st.title("CleanIntel – UK Tender Intelligence")
st.caption("Fuzzy search in title or buyer + scoring (time + value + recency).")

# ---- Supabase connection from Streamlit Secrets (ENV) ----
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ========= Helpers =========

SCORE_MAP = {"S": 100, "A": 75, "B": 50, "C": 30, "F": 0}
TIER_BADGE = {"S": "🟩", "A": "🟢", "B": "🟡", "C": "🟠", "F": "🟥"}

def safe_float(v):
    try:
        return float(v)
    except Exception:
        return None

def safe_buyer_name(v):
    if isinstance(v, dict):
        # pull common keys if buyer is JSON
        return v.get("name") or v.get("buyerName") or ""
    if isinstance(v, str):
        return v
    return ""

def parse_first_present(df: pd.DataFrame, cols):
    out = None
    for c in cols:
        if c in df.columns:
            out = df[c] if out is None else out.fillna(df[c])
    return out

def compute_score_tier(days_left: float | None, value_gbp: float | None, recency_days: float | None) -> str:
    """
    Time bands (base):
      >21 days -> A (high-chance window)
      7–21     -> B
      2–6      -> C
      <2 days  -> F
    Value uplift (>= £250k):
      A->S, B->A, C->B, F stays F
    Recency penalty (published > 40 days ago):
      S->A, A->B
    """
    # time → base tier
    if days_left is None:
        base = "C"
    else:
        if days_left > 21:
            base = "A"
        elif days_left >= 7:
            base = "B"
        elif days_left >= 2:
            base = "C"
        else:
            base = "F"

    # value uplift
    hv = (safe_float(value_gbp) is not None and safe_float(value_gbp) >= 250000.0)
    if hv:
        if base == "A":
            base = "S"
        elif base == "B":
            base = "A"
        elif base == "C":
            base = "B"

    # recency penalty
    if recency_days is not None and recency_days > 40:
        if base == "S":
            base = "A"
        elif base == "A":
            base = "B"

    return base

# ========= UI =========

st.subheader("Search UK Government Tenders")
keyword = st.text_input("Keyword (fuzzy match in title OR buyer, e.g., cleaning, school, waste, solar)")

if keyword:
    # We avoid .or_ SDK differences by doing two ilike queries and merging in pandas
    base_select = "title,buyer,value_gbp,status,deadline,published_date,date_published"

    # title ilike
    r1 = (
        supabase.table("tenders")
        .select(base_select)
        .ilike("title", f"%{keyword}%")
        .execute()
    )
    data1 = r1.data or []

    # buyer ilike
    r2 = (
        supabase.table("tenders")
        .select(base_select)
        .ilike("buyer", f"%{keyword}%")
        .execute()
    )
    data2 = r2.data or []

    rows = (data1 or []) + (data2 or [])
    if not rows:
        st.warning("No tenders found.")
    else:
        df = pd.DataFrame(rows).copy()

        # Normalize buyer to plain text
        if "buyer" in df.columns:
            df["buyer"] = df["buyer"].apply(safe_buyer_name)
        else:
            df["buyer"] = ""

        # Ensure value_gbp numeric
        if "value_gbp" not in df.columns:
            df["value_gbp"] = None
        df["value_gbp"] = df["value_gbp"].apply(safe_float)

        # Dates → UTC
        now_utc = datetime.now(timezone.utc)
        if "deadline" in df.columns:
            df["deadline"] = pd.to_datetime(df["deadline"], errors="coerce", utc=True)
        else:
            df["deadline"] = pd.NaT

        pub_series = parse_first_present(df, ["published_date", "date_published"])
        if pub_series is None:
            df["published_dt"] = pd.NaT
        else:
            df["published_dt"] = pd.to_datetime(pub_series, errors="coerce", utc=True)

        # Calculate days_left and recency_days
        def days_left_fn(d):
            if pd.isna(d):
                return None
            return (d - now_utc).total_seconds() / 86400.0

        def recency_days_fn(d):
            if pd.isna(d):
                return None
            return (now_utc - d).total_seconds() / 86400.0

        df["days_left"] = df["deadline"].apply(days_left_fn)
        df["recency_days"] = df["published_dt"].apply(recency_days_fn)

        # Drop duplicates from merging title/buyer hits (by title + deadline combo)
        if "title" in df.columns and "deadline" in df.columns:
            df = df.sort_values("value_gbp", ascending=False)
            df = df.drop_duplicates(subset=["title", "deadline"], keep="first")

        # Compute score
        df["score_tier"] = df.apply(lambda r: compute_score_tier(r["days_left"], r["value_gbp"], r["recency_days"]), axis=1)
        df["score_value"] = df["score_tier"].map(SCORE_MAP).fillna(0).astype(int)
        df["score"] = df.apply(lambda r: f"{TIER_BADGE.get(r['score_tier'],'')} {r['score_tier']} ({int(r['score_value'])})", axis=1)

        # Final order (your requested five + score columns at end)
        desired = ["title", "buyer", "value_gbp", "status", "deadline", "score", "score_tier", "score_value"]
        df = df.reindex(columns=[c for c in desired if c in df.columns])

        # Default sort: money first (your choice B)
        if "value_gbp" in df.columns:
            df = df.sort_values(by=["value_gbp"], ascending=False)

        st.success(f"Found {len(df)} results for “{keyword}”")
        st.dataframe(df, use_container_width=True)

        with st.expander("ⓘ Scoring Model (v1 heuristic)"):
            st.markdown(
                """
**How we score (v1):**  
We prioritise tenders with **more than 21 days** left and **higher value (≥ £250k)**.

- **Time window (base tier):**  
  • > 21 days → A (high-chance)  
  • 7–21 days → B  
  • 2–6 days → C  
  • < 2 days → F  

- **Value uplift (≥ £250k):**  
  • A → **S**, B → **A**, C → **B** (F stays F)

- **Recency penalty:**  
  • If published > 40 days ago: **S → A**, **A → B**

- **Score values:** S=100, A=75, B=50, C=30, F=0
                """
            )
