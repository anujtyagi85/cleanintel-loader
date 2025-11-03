# cleanintel_app.py
import os
import datetime as dt
from typing import Optional, Tuple, List

import streamlit as st

# ---- Supabase client ----
from supabase import create_client, Client

# Optional fuzzy: we'll gracefully fall back if missing
try:
    from rapidfuzz import fuzz, process
    HAVE_RAPIDFUZZ = True
except Exception:
    HAVE_RAPIDFUZZ = False


# ------------- Config / Secrets -------------
def get_supabase() -> Client:
    # Prefer Streamlit secrets, then env
    url = os.environ.get("SUPABASE_URL") or st.secrets.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY") or st.secrets.get("SUPABASE_KEY") or st.secrets.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        st.error("Supabase URL/KEY not configured. Add SUPABASE_URL and SUPABASE_KEY in Streamlit secrets.")
        st.stop()
    return create_client(url, key)


supabase = get_supabase()

APP_TITLE = "🧠 CleanIntel • Smart Tender Assistant"

# Default quotas if not set in DB
DEFAULT_FREE_QUOTA = 5
DEFAULT_PRO_QUOTA = 50

# Fuzzy match threshold (0-100)
FUZZY_THRESHOLD = 60

# ------------- Helpers -------------
def month_yyyymm(date: dt.date) -> str:
    return f"{date.year:04d}-{date.month:02d}"

def ensure_usage_row(email: str) -> dict:
    """
    Ensures a user_usage row exists for this email.
    Auto-creates a Free plan row if missing.
    Also auto-resets searches_used when month changes.
    """
    # get or create
    data = supabase.table("user_usage").select("*").eq("email", email).limit(1).execute().data
    today = dt.date.today()

    if not data:
        # Create a default row: Free plan
        row = {
            "email": email,
            "plan": "Free",
            "monthly_quota": DEFAULT_FREE_QUOTA,
            "searches_used": 0,
            "last_reset": today.isoformat()
        }
        supabase.table("user_usage").insert(row).execute()
        return row

    row = data[0]

    # Auto-reset searches when month flips
    try:
        last_reset = dt.date.fromisoformat(row.get("last_reset") or today.isoformat())
    except Exception:
        last_reset = today

    if month_yyyymm(last_reset) != month_yyyymm(today):
        # Reset counter for new month
        row["searches_used"] = 0
        row["last_reset"] = today.isoformat()
        supabase.table("user_usage") \
            .update({"searches_used": 0, "last_reset": today.isoformat()}) \
            .eq("email", email).execute()

    return row

def get_plan_quota(row: dict) -> Tuple[str, int, int]:
    """
    Returns (plan, used, quota)
    If monthly_quota set, use it; else defaults.
    """
    plan = (row.get("plan") or "Free").strip()
    used = int(row.get("searches_used") or 0)

    # Prefer DB column if present
    quota = row.get("monthly_quota")
    if quota is not None:
        try:
            quota = int(quota)
        except Exception:
            quota = None

    if quota is None:
        quota = DEFAULT_PRO_QUOTA if plan.lower() == "pro" else DEFAULT_FREE_QUOTA

    return plan, used, quota

def increment_usage(email: str) -> None:
    row = ensure_usage_row(email)
    used = int(row.get("searches_used") or 0) + 1
    supabase.table("user_usage").update({"searches_used": used}).eq("email", email).execute()

def log_search(email: str, query: str) -> None:
    try:
        supabase.table("search_logs").insert({"email": email, "query": query}).execute()
    except Exception:
        # don't block the UX if logging fails
        pass

def fuzzy_filter_titles(query: str, rows: List[dict]) -> List[dict]:
    """
    Fuzzy matches 'query' against rows' 'title' field.
    Returns rows with a 'score' added, sorted desc.
    """
    q = (query or "").strip()
    if not q:
        return []

    titles = [(r.get("title") or "").strip() for r in rows]

    if HAVE_RAPIDFUZZ:
        # Build scoring
        scored: List[Tuple[str, float, int]] = process.extract(
            q,
            titles,
            scorer=fuzz.token_set_ratio,
            score_cutoff=FUZZY_THRESHOLD,
            limit=None,
        )
        # scored: list of (matched_title, score, index)
        results = []
        for _, score, idx in scored:
            r = dict(rows[idx])  # copy
            r["score"] = int(score)
            results.append(r)
        # Sort by score desc, then by published_date desc if present
        results.sort(key=lambda r: (r.get("score", 0), str(r.get("published_date") or "")), reverse=True)
        return results

    # Fallback: simple substring case-insensitive
    results = []
    qlower = q.lower()
    for r in rows:
        title = (r.get("title") or "")
        if qlower in title.lower():
            r2 = dict(r)
            r2["score"] = 100  # treat as perfect match
            results.append(r2)
    results.sort(key=lambda r: str(r.get("published_date") or ""), reverse=True)
    return results

def fetch_tenders_for_matching(limit: int = 5000) -> List[dict]:
    # Pull minimal useful columns to keep transfer light.
    # Adjust columns to whatever your table has available.
    cols = [
        "title",
        "published_date",
        "deadline",
        "value_text",
        "tender_id",
        "buyer"  # jsonb, may be null
    ]
    try:
        resp = supabase.table("tenders").select(",".join(cols)).limit(limit).execute()
        return resp.data or []
    except Exception as e:
        st.error(f"Error fetching tenders: {e}")
        return []

def buyer_name_from_json(buyer) -> str:
    if isinstance(buyer, dict):
        # Often the JSON stores a "name" field
        return str(buyer.get("name") or buyer.get("buyer") or "").strip()
    return ""

# ------------- Auth -------------
def do_signup(email: str, password: str) -> Optional[str]:
    try:
        res = supabase.auth.sign_up({"email": email, "password": password})
        # Supabase may require email confirmation depending on project settings
        return None
    except Exception as e:
        return str(e)

def do_login(email: str, password: str) -> Optional[str]:
    try:
        res = supabase.auth.sign_in_with_password({"email": email, "password": password})
        if not res or not res.user:
            return "Invalid credentials."
        return None
    except Exception as e:
        return str(e)


# ------------- UI -------------
st.set_page_config(page_title="CleanIntel", page_icon="🧠", layout="wide")
st.title(APP_TITLE)

if "user_email" not in st.session_state:
    st.session_state.user_email = None

# Auth pane
if not st.session_state.user_email:
    with st.expander("🔐 Login / Signup", expanded=True):
        tab1, tab2 = st.tabs(["Login", "Create account"])

        with tab1:
            login_email = st.text_input("Email", key="login_email")
            login_pw = st.text_input("Password", type="password", key="login_pw")
            if st.button("Login"):
                if not login_email or not login_pw:
                    st.warning("Please enter email and password.")
                else:
                    err = do_login(login_email, login_pw)
                    if err:
                        st.error(f"Login failed: {err}")
                    else:
                        st.session_state.user_email = login_email
                        st.success("Logged in!")

        with tab2:
            reg_email = st.text_input("Email", key="reg_email")
            reg_pw = st.text_input("Password", type="password", key="reg_pw")
            if st.button("Create account"):
                if not reg_email or not reg_pw:
                    st.warning("Please enter email and password.")
                else:
                    err = do_signup(reg_email, reg_pw)
                    if err:
                        st.error(f"Signup failed: {err}")
                    else:
                        # Create usage row immediately so plan/quota are visible
                        ensure_usage_row(reg_email)
                        st.info("Signup successful. Please check your inbox if email confirmation is required, then login.")
    st.stop()

# Logged-in panel
left, right = st.columns([1, 3])
with left:
    st.caption("Logged in as")
    st.markdown(f"**{st.session_state.user_email}**")

    usage_row = ensure_usage_row(st.session_state.user_email)
    plan, used, quota = get_plan_quota(usage_row)

    st.metric("Plan", plan)
    st.metric("Searches used", f"{used}/{quota}")

    if st.button("Logout"):
        st.session_state.user_email = None
        try:
            supabase.auth.sign_out()
        except Exception:
            pass
        st.experimental_rerun()

with right:
    st.write("Find public **cleaning tenders** faster and smarter — free for your first searches each month.")
    query = st.text_input("Describe what you're looking for", placeholder="e.g. NHS cleaning, floor scrubber, janitorial")

    if st.button("Search", type="primary"):
        if not query.strip():
            st.warning("Please enter a search term.")
        else:
            # Enforce quota before search
            usage_row = ensure_usage_row(st.session_state.user_email)
            plan, used, quota = get_plan_quota(usage_row)

            if used >= quota:
                st.error(f"You've reached your monthly quota ({used}/{quota}). Upgrade plan to continue.")
            else:
                # Record usage + log
                increment_usage(st.session_state.user_email)
                log_search(st.session_state.user_email, query)
                st.success(f"Search recorded ✅ ({used+1}/{quota})")

                # Fetch candidates and fuzzy match
                rows = fetch_tenders_for_matching(limit=5000)
                matched = fuzzy_filter_titles(query, rows)

                if not matched:
                    st.info("No tenders matched. Try a broader term.")
                else:
                    # Prepare a neat table
                    out = []
                    for r in matched[:300]:  # cap display
                        out.append({
                            "Score": r.get("score"),
                            "Title": r.get("title"),
                            "Buyer": buyer_name_from_json(r.get("buyer")),
                            "Published": r.get("published_date"),
                            "Deadline": r.get("deadline"),
                            "Value": r.get("value_text"),
                            "Tender ID": r.get("tender_id"),
                        })
                    st.dataframe(out, use_container_width=True)

# Footer
st.caption(
    "Tip: Results use fuzzy matching"
    + (" (RapidFuzz)" if HAVE_RAPIDFUZZ else " (basic substring fallback)")
    + f" at threshold {FUZZY_THRESHOLD}."
)
