import os
from datetime import datetime, timezone
import pandas as pd
import streamlit as st
from supabase import create_client

st.set_page_config(page_title="CleanIntel – UK Tender Intelligence", layout="wide")
st.title("CleanIntel – UK Tender Intelligence")
st.caption("Fuzzy search in title or buyer + scoring (time + value + recency).")

# ---- Supabase connection (Streamlit Cloud -> Secrets) ----
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

def safe_buyer_text(v):
    if isinstance(v, dict):
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
    # value uplift (>= £250k)
    hv = (safe_float(value_gbp) is not None and safe_float(value_gbp) >= 250000.0)
    if hv:
        if base == "A":
            base = "S"
        elif base == "B":
            base = "A"
        elif base == "C":
            base = "B"
    # recency penalty (> 40 days old)
    if recency_days is not None and recency_days > 40:
        if base == "S":
            base = "A"
        elif base == "A":
            base = "B"
    return base

def buyer_contains(row_buyer, kw_lower: str) -> bool:
    txt = safe_buyer_text(row_buyer).lower()
    return kw_lower in txt if txt else False

# ========= UI =========
st.subheader("Search UK Government Tenders")
keyword = st.text_input("Keyword (fuzzy match in title OR buyer, e.g., cleaning, school, waste, solar)")

if keyword:
    kw = keyword.strip()
    kw_lower = kw.lower()
    base_select = "title,buyer,value_gbp,status,deadline,published_date,date_published"

    # --- 1) Server-side title ILIKE (safe for text columns)
    r_title = (
        supabase.table("tenders")
        .select(base_select)
        .ilike("title", f"%{kw}%")
        .execute()
    )
    data_title = r_title.data or []

    # --- 2) Try server-side buyer ILIKE (may fail if buyer is JSONB)
    data_buyer = []
    buyer_ilike_ok = True
    try:
        r_buyer = (
            supabase.table("tenders")
            .select(base_select)
            .ilike("buyer", f"%{kw}%")
            .execute()
        )
        data_buyer = r_buyer.data or []
    except Exception:
        buyer_ilike_ok = False

    # --- 3) If buyer ILIKE failed, pull recent and filter buyer in pandas
    data_fallback = []
    if not buyer_ilike_ok:
        try:
            r_recent = (
                supabase.table("tenders")
                .select(base_select)
                .order("published_date", desc=True)  # safe even if nulls
                .limit(1000)
                .execute()
            )
            data_fallback = [row for row in (r_recent.data or []) if buyer_contains(row.get("buyer"), kw_lower)]
        except Exception:
            data_fallback = []

    rows = (data_title or []) + (data_buyer or []) + (data_fallback or [])

    if not rows:
        st.warning("No tenders found.")
    else:
        df = pd.DataFrame(rows).copy()

        # Normalize buyer to plain text
        if "buyer" in df.columns:
            df["buyer"] = df["buyer"].apply(safe_buyer_text)
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

        # Derived metrics
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

        # De-dup results from title & buyer matches
        if "title" in df.columns and "deadline" in df.columns:
            df = df.sort_values("value_gbp", ascending=False)
            df = df.drop_duplicates(subset=["title", "deadline"], keep="first")

        # Scoring
        df["score_tier"] = df.apply(lambda r: compute_score_tier(r["days_left"], r["value_gbp"], r["recency_days"]), axis=1)
        df["score_value"] = df["score_tier"].map(SCORE_MAP).fillna(0).astype(int)
        df["score"] = df.apply(lambda r: f"{TIER_BADGE.get(r['score_tier'],'')} {r['score_tier']} ({int(r['score_value'])})", axis=1)

        # Final order + default sort (value desc)
        desired = ["title", "buyer", "value_gbp", "status", "deadline", "score", "score_tier", "score_value"]
        df = df.reindex(columns=[c for c in desired if c in df.columns])
        if "value_gbp" in df.columns:
            df = df.sort_values(by=["value_gbp"], ascending=False)

        st.success(f"Found {len(df)} results for “{keyword}”")
        st.dataframe(df, use_container_width=True)

        with st.expander("ⓘ Scoring Model (v1 heuristic)"):
            st.markdown(
                """
**How we score (v1):**

- **Time window (base tier)**  
  >21d → A, 7–21d → B, 2–6d → C, <2d → F

- **Value uplift (≥ £250k)**  
  A→S, B→A, C→B (F stays F)

- **Recency penalty**  
  If published >40d ago: S→A, A→B

- **Numeric score**  
  S=100, A=75, B=50, C=30, F=0
                """
            )
