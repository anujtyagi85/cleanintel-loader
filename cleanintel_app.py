# cleanintel_app.py
# CleanIntel – Smart Tender Assistant (freemium, no OpenAI/Stripe)
# Streamlit 1.50 compatible

import os
import datetime as dt
from typing import Optional, Tuple, List

import streamlit as st
from supabase import create_client, Client
from dotenv import load_dotenv

# ---------- Config & Setup ----------

st.set_page_config(page_title="CleanIntel • Smart Tender Assistant", page_icon="🧠", layout="wide")

load_dotenv(override=True)

def get_secret(key: str, default: Optional[str] = None) -> Optional[str]:
    # Prefer env, fallback to .streamlit/secrets.toml
    val = os.environ.get(key)
    if val:
        return val
    try:
        return st.secrets.get(key, default)  # type: ignore[attr-defined]
    except Exception:
        return default

SUPABASE_URL = get_secret("SUPABASE_URL")
SUPABASE_KEY = get_secret("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("Missing Supabase credentials. Please set SUPABASE_URL and SUPABASE_KEY in env or .streamlit/secrets.toml.")
    st.stop()

def get_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

sb: Client = get_supabase()

# --- Constants
FREE_PLAN = "free"
PRO_PLAN = "pro"
FREE_QUOTA = 5
PRO_QUOTA = 500

# --- Session helpers
def get_state(key: str, default=None):
    if key not in st.session_state:
        st.session_state[key] = default
    return st.session_state[key]

def set_state(key: str, value):
    st.session_state[key] = value

# ---------- Auth Logic ----------

def do_signup(email: str, password: str) -> Tuple[bool, str]:
    try:
        # Create auth user
        res = sb.auth.sign_up({"email": email, "password": password})
        # Prepare/ensure usage row for this user (may not have id yet if email not confirmed)
        # Try to upsert by email; once user confirms, the UUID will be used next login.
        ensure_user_usage_row(email=email, user_id=None)
        return True, "Signup successful. Check your inbox to confirm your email."
    except Exception as e:
        return False, f"Signup failed: {e}"

def do_login(email: str, password: str) -> Tuple[bool, str]:
    try:
        res = sb.auth.sign_in_with_password({"email": email, "password": password})
        user = res.user
        if not user:
            return False, "Login failed: no user returned."
        set_state("user", {"id": user.id, "email": user.email})
        # Make sure usage row exists/updated for this user id
        ensure_user_usage_row(email=user.email, user_id=user.id)
        return True, "Logged in."
    except Exception as e:
        return False, f"Login failed: {e}"

def do_logout():
    try:
        sb.auth.sign_out()
    except Exception:
        pass
    if "user" in st.session_state:
        del st.session_state["user"]
    st.rerun()

# ---------- user_usage enforcement ----------

def month_start(d: dt.date) -> dt.date:
    return dt.date(d.year, d.month, 1)

def ensure_user_usage_row(email: Optional[str], user_id: Optional[str]):
    """
    Ensures a row exists in public.user_usage for this user.
    Columns expected:
      id (uuid, PK, nullable), email (text), plan (text), searches_used (int),
      monthly_quota (int), last_reset (date)
    We upsert by email if id is unknown, then later update id when known.
    """
    today = dt.date.today()

    # Fetch existing by user_id first
    row = None
    if user_id:
        res = sb.table("user_usage").select("*").eq("id", user_id).limit(1).execute()
        row = (res.data or [None])[0]
    if not row and email:
        res = sb.table("user_usage").select("*").eq("email", email).limit(1).execute()
        row = (res.data or [None])[0]

    # Prepare defaults
    defaults = {
        "email": email,
        "plan": FREE_PLAN,
        "searches_used": 0,
        "monthly_quota": FREE_QUOTA,
        "last_reset": str(month_start(today)),
    }

    if not row:
        # Insert a new row – if user_id exists, set it as id
        payload = defaults.copy()
        if user_id:
            payload["id"] = user_id
        sb.table("user_usage").insert(payload).execute()
        return

    # If exists, make sure id/email present and reset month if needed
    updates = {}
    if user_id and not row.get("id"):
        updates["id"] = user_id
    if email and row.get("email") != email:
        updates["email"] = email

    # Handle month reset
    try:
        last_reset = row.get("last_reset")
        if isinstance(last_reset, str):
            last_reset_date = dt.date.fromisoformat(last_reset)
        elif last_reset:
            # supabase may return date already parsed; be defensive
            last_reset_date = dt.date.fromisoformat(str(last_reset))
        else:
            last_reset_date = month_start(today)
    except Exception:
        last_reset_date = month_start(today)

    if month_start(today) != last_reset_date:
        updates["searches_used"] = 0
        updates["last_reset"] = str(month_start(today))

    # Ensure plan/quota sane
    plan = row.get("plan") or FREE_PLAN
    quota = row.get("monthly_quota") or (PRO_QUOTA if plan == PRO_PLAN else FREE_QUOTA)
    if row.get("plan") != plan:
        updates["plan"] = plan
    if row.get("monthly_quota") != quota:
        updates["monthly_quota"] = quota

    if updates:
        sb.table("user_usage").update(updates).eq("email", email).execute()

def get_usage(email: str) -> Tuple[int, int, str]:
    """
    Returns (searches_used, monthly_quota, plan)
    """
    res = sb.table("user_usage").select("searches_used, monthly_quota, plan").eq("email", email).limit(1).execute()
    row = (res.data or [None])[0]
    if not row:
        # create default if somehow missing
        ensure_user_usage_row(email=email, user_id=None)
        return (0, FREE_QUOTA, FREE_PLAN)
    return (row.get("searches_used") or 0, row.get("monthly_quota") or FREE_QUOTA, row.get("plan") or FREE_PLAN)

def increment_usage(email: str):
    res = sb.table("user_usage").select("searches_used").eq("email", email).limit(1).execute()
    row = (res.data or [None])[0]
    current = (row or {}).get("searches_used") or 0
    sb.table("user_usage").update({"searches_used": current + 1}).eq("email", email).execute()

# ---------- Query tenders ----------

def search_tenders_simple(q: str, limit: int = 20) -> List[dict]:
    """
    Keyword search across title/description/buyer (buyer treated as TEXT),
    ordered by most recently published first.
    """
    q = q.strip()
    if not q:
        return []

    pattern = f"%{q}%"

    # We try to OR across the 3 columns. supabase-py uses .or_ for filters.
    query = (
        sb.table("tenders")
          .select("title, description, buyer, value_normalized, currency, published_date, deadline, notice_url, tender_id")
          .or_(f"title.ilike.{pattern},description.ilike.{pattern},buyer.ilike.{pattern}")
          .order("published_date", desc=True, nulls_first=False)
          .limit(limit)
    )
    res = query.execute()
    return res.data or []

# ---------- UI Sections ----------

def header_bar():
    st.markdown("### 🧠 CleanIntel • Smart Tender Assistant")

def hero_pricing():
    st.write("Find **public cleaning tenders** faster and smarter — free for your first **5 searches each month**.")
    left, right = st.columns([1, 3])
    with left:
        st.button("🔐 Login / Signup", on_click=lambda: set_state("show_auth", True))
    st.markdown("### Pricing Plans")
    st.table(
        {
            "Plan": ["Free", "Pro"],
            "Price": ["£0", "£20/mo"],
            "Features": ["5 searches/month", "500 searches + filters"],
        }
    )

def auth_screen():
    st.markdown("## 🔑 CleanIntel Login / Signup")
    tabs = st.tabs(["Login", "Create account"])

    with tabs[0]:
        with st.form("login"):
            email = st.text_input("Email", key="login_email")
            pw = st.text_input("Password", type="password", key="login_pw")
            submitted = st.form_submit_button("Continue")
            if submitted:
                ok, msg = do_login(email, pw)
                if ok:
                    st.success(msg)
                    set_state("show_auth", False)
                    st.rerun()
                else:
                    st.error(msg)

    with tabs[1]:
        with st.form("signup"):
            email = st.text_input("Email", key="signup_email")
            pw = st.text_input("Password", type="password", key="signup_pw")
            submitted = st.form_submit_button("Create account")
            if submitted:
                ok, msg = do_signup(email, pw)
                if ok:
                    st.success(msg)
                else:
                    st.error(msg)

def app_screen():
    user = get_state("user")
    if not user:
        st.warning("You’re not logged in.")
        return

    email = user.get("email")
    searches_used, monthly_quota, plan = get_usage(email)

    with st.sidebar:
        st.caption(f"Logged in as\n**{email}**")
        st.write(f"**Plan:** {plan.capitalize()}")
        st.write(f"**Searches used:** {searches_used}/{monthly_quota}")
        if st.button("Logout"):
            do_logout()

    st.write("Describe what you're looking for")
    q = st.text_input("e.g. nhs cleaning tenders in UK", key="query", label_visibility="collapsed")
    c1, c2 = st.columns([1, 4])
    with c1:
        search = st.button("Search", type="primary")

    if search:
        # enforce quota
        if searches_used >= monthly_quota:
            st.error("You’ve reached your monthly search limit. Upgrade to Pro for 500 searches & filters (coming soon).")
            return

        results = []
        try:
            results = search_tenders_simple(q, limit=30)
        except Exception as e:
            st.error(f"Search failed: {e}")
            return

        # Increment usage only on successful query
        increment_usage(email)
        st.success(f"Search recorded ✅ ({searches_used + 1}/{monthly_quota})")

        if not results:
            st.info("No tenders matched that query. Try different keywords.")
            return

        # Show results
        st.markdown("### Results")
        for row in results:
            with st.container(border=True):
                title = row.get("title") or "Untitled"
                buyer = row.get("buyer") or "—"
                val = row.get("value_normalized")
                currency = row.get("currency") or ""
                pub = row.get("published_date") or ""
                deadline = row.get("deadline") or ""
                url = row.get("notice_url") or ""
                desc = row.get("description") or ""

                line1 = f"**{title}**"
                if buyer and buyer != "—":
                    line1 += f"  \n**Buyer:** {buyer}"

                st.markdown(line1)

                meta = []
                if val:
                    try:
                        # pretty value
                        meta.append(f"**Value:** {currency}{int(float(val)):,}")
                    except Exception:
                        meta.append(f"**Value:** {currency}{val}")
                if pub:
                    meta.append(f"**Published:** {pub}")
                if deadline:
                    meta.append(f"**Deadline:** {deadline}")

                if meta:
                    st.caption(" • ".join(meta))

                if desc:
                    st.write(desc[:350] + ("…" if len(desc) > 350 else ""))

                if url:
                    st.link_button("View notice", url)

# ---------- Main Router ----------

def main():
    header_bar()

    user = get_state("user")
    show_auth = get_state("show_auth", False)

    if not user and not show_auth:
        # Home (logged-out)
        hero_pricing()
        return

    if show_auth and not user:
        auth_screen()
        return

    # Logged-in app
    app_screen()

if __name__ == "__main__":
    main()
