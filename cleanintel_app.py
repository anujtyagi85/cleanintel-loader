import os
import pandas as pd
import streamlit as st
from datetime import datetime, timezone
from supabase import create_client

st.set_page_config(page_title="CleanIntel – UK Tender Intelligence", layout="wide")

st.title("CleanIntel – UK Tender Intelligence")
st.caption("Search tenders and see chance/priority scoring (v1 heuristic).")

# ---- Supabase connection via Streamlit Secrets (ENV) ----
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ---- UI: search ----
st.subheader("Search UK Government Tenders")
keyword = st.text_input("Keyword (e.g., cleaning, school, waste, solar, carpets, catering)")

# ---- scoring helpers ----
def compute_score_tier(days_left: float, value_gbp: float, recency_days: float | None) -> str:
    """
    Tier logic (time + value + recency):
      Time bands:
        >21 days       -> base A (high-chance window)
        7–21 days      -> base B
        2–6 days       -> base C
        <48 hours      -> base F

      Value uplift (>= £250k):
        If base A -> S
        If base B -> A
        If base C -> B
        F stays F

      Recency penalty (if published too old):
        If recency_days is known and > 40 days:
            S -> A, A -> B  (don’t penalize below B)
    """
    # base by time
    if days_left is None:
        base = "C"  # unknown deadline -> conservative
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
    try:
        high_value = (float(value_gbp) >= 250000.0)
    except Exception:
        high_value = False

    if high_value:
        if base == "A":
            base = "S"
        elif base == "B":
            base = "A"
        elif base == "C":
            base = "B"
        # F remains F

    # recency penalty
    if recency_days is not None and recency_days > 40:
        if base == "S":
            base = "A"
        elif base == "A":
            base = "B"

    return base


SCORE_MAP = {"S": 100, "A": 75, "B": 50, "C": 30, "F": 0}
TIER_BADGE = {"S": "🟩", "A": "🟢", "B": "🟡", "C": "🟠", "F": "🟥"}


def parse_first_present(df: pd.DataFrame, cols: list[str]) -> pd.Series:
    """Return the first non-null column among cols; else NaT/None."""
    out = None
    for c in cols:
        if c in df.columns:
            if out is None:
                out = df[c]
            else:
                out = out.fillna(df[c])
    return out


def safe_buyer_to_name(val):
    """buyer might be string, dict, None."""
    if isinstance(val, dict):
        return val.get("name") or val.get("buyerName") or ""
    if isinstance(val, str):
        return val
    return ""


# ---- Query + Transform ----
if keyword:
    # Ask for multiple possible publish-date columns; we’ll pick whichever exists.
    # Also include notice_url if present (not displayed yet, but useful later).
query = (
    supabase.table("tenders")
    .select("title,buyer,value_gbp,status,deadline,notice_url,published_date,date_published")
    .ilike("title", f"%{keyword}%")
)
    response = query.execute()
    rows = response.data or []

    if not rows:
        st.warning("No tenders found.")
    else:
        df = pd.DataFrame(rows)

        # Normalize buyer to a simple text name
        if "buyer" in df.columns:
            df["buyer"] = df["buyer"].apply(safe_buyer_to_name)
        else:
            df["buyer"] = ""

        # Dates → UTC
        now_utc = datetime.now(timezone.utc)

        # Deadline
        if "deadline" in df.columns:
            df["deadline"] = pd.to_datetime(df["deadline"], errors="coerce", utc=True)
        else:
            df["deadline"] = pd.NaT

        # Published date: prefer 'published_date', fallback 'date_published'
        pub_series = parse_first_present(df, ["published_date", "date_published"])
        if pub_series is None:
            df["published_dt"] = pd.NaT
        else:
            df["published_dt"] = pd.to_datetime(pub_series, errors="coerce", utc=True)

        # Days left & recency
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

        # Clean value_gbp to float
        def to_float(v):
            try:
                return float(v)
            except Exception:
                return None

        df["value_gbp"] = df["value_gbp"].apply(to_float)

        # Compute tier + score
        df["score_tier"] = df.apply(
            lambda r: compute_score_tier(r["days_left"], r["value_gbp"], r["recency_days"]),
            axis=1,
        )
        df["score_value"] = df["score_tier"].map(SCORE_MAP).fillna(0).astype(int)
        df["badge"] = df["score_tier"].map(TIER_BADGE).fillna("")

        # Human-friendly short score column (emoji + number)
        df["score"] = df["badge"] + " " + df["score_tier"] + f" ({'{:d}'.format(0)})"
        # fix numeric inside string
        df["score"] = df.apply(lambda r: f"{TIER_BADGE.get(r['score_tier'],'')} {r['score_tier']} ({int(r['score_value'])})", axis=1)

        # Final order: title, buyer, value_gbp, status, deadline, score_tier, score_value
        show_cols = ["title", "buyer", "value_gbp", "status", "deadline", "score", "score_tier", "score_value"]
        df = df.reindex(columns=[c for c in show_cols if c in df.columns])

        # Default sort: highest-priority first (S/A before others), then highest value, then farthest deadline
        tier_rank = {"S": 0, "A": 1, "B": 2, "C": 3, "F": 4}
        df["_tier_rank"] = df["score_tier"].map(tier_rank).fillna(9)
        df = df.sort_values(by=["_tier_rank", "value_gbp", "deadline"], ascending=[True, False, False]).drop(columns=["_tier_rank"])

        st.success(f"Found {len(df)} tenders for “{keyword}”")
        st.dataframe(df, use_container_width=True)

        # Tiny explainer for your model (trust-building)
        with st.expander("ⓘ Scoring Model (v1 heuristic)"):
            st.markdown(
                """
**How we score (v1):**  
We prioritize tenders with **more than 21 days** to go and **higher value (≥ £250k)**.

- **Time window → base tier**  
  • > 21 days → A (high-chance window)  
  • 7–21 days → B  
  • 2–6 days → C  
  • < 48 hours → F  

- **Value uplift (≥ £250k)**  
  • A → **S**, B → **A**, C → **B** (F stays F)

- **Recency penalty (stale publish)**  
  • If published > 40 days ago: **S → A**, **A → B**.

- **Score values:** S=100, A=75, B=50, C=30, F=0
                """
            )
