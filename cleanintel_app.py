# cleanintel_app.py
import os
import datetime as dt
from typing import Optional, Tuple

import streamlit as st

# Supabase Py v2
from supabase import create_client, Client
from supabase.lib.client_options import ClientOptions
from postgrest.exceptions import APIError

APP_TITLE = "🧠 CleanIntel • Smart Tender Assistant"
FREE_QUOTA = 5
PRO_QUOTA = 50

# -----------------------------
# Supabase bootstrap
# -----------------------------
@st.cache_resource(show_spinner=False)
def get_supabase() -> Client:
    url = os.getenv("SUPABASE_URL") or st.secrets.get("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY") or st.secrets.get("SUPABASE_KEY")
    if not url or not key:
        st.error("Missing Supabase credentials. Please add SUPABASE_URL and SUPABASE_KEY.")
        st.stop()
    return create_client(url, key, options=ClientOptions(schema="public"))

sb = get_supabase()


# -----------------------------
# Helpers
# -----------------------------
def start_of_this_month() -> dt.date:
    now = dt.date.today()
    return dt.date(now.year, now.month, 1)

def today() -> dt.date:
    return dt.date.today()

def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


# -----------------------------
# Auth UI
# -----------------------------
def auth_screen():
    tabs = st.tabs(["Login", "Create account"])
    with tabs[0]:
        login_form()
    with tabs[1]:
        signup_form()


def login_form():
    st.subheader("Login")
    with st.form("login_form", clear_on_submit=False):
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")
        submitted = st.form_submit_button("Login")

    if submitted:
        email_n = normalize_email(email)
        try:
            sb.auth.sign_in_with_password({"email": email_n, "password": password})
            st.success("Logged in. Redirecting…")
            st.session_state["logged_in_email"] = email_n
            st.rerun()
        except Exception as e:
            st.error(f"Login failed: {str(e)}")


def signup_form():
    st.subheader("Create account")
    with st.form("signup_form", clear_on_submit=False):
        email = st.text_input("Email", key="signup_email")
        password = st.text_input("Password", type="password", key="signup_password")
        submitted = st.form_submit_button("Create account")

    if submitted:
        email_n = normalize_email(email)
        try:
            # Create auth user (Supabase will email a confirmation link)
            sb.auth.sign_up({"email": email_n, "password": password})
            st.success("Signup successful. Check your inbox to confirm your email.")

            # Ensure a usage row exists (id uuid default, last_reset date, searches_used int, monthly_quota int, plan text, email text UNIQUE)
            # We use UPSERT-like behavior: try insert; if unique violation, just ignore.
            try:
                sb.table("user_usage").insert({
                    "email": email_n,
                    "plan": "free",
                    "monthly_quota": FREE_QUOTA,
                    "searches_used": 0,
                    "last_reset": today().isoformat(),
                }).execute()
            except APIError as api_err:
                # If unique or null issues, ignore; otherwise bubble up
                msg = str(api_err).lower()
                if "duplicate key" in msg or "unique" in msg:
                    pass
                else:
                    raise

        except Exception as e:
            st.error(f"Signup failed: {str(e)}")


# -----------------------------
# Usage / Quota handling
# -----------------------------
def fetch_or_create_usage(email: str) -> Optional[dict]:
    """Get the user_usage row. If missing, create as free with defaults."""
    email_n = normalize_email(email)
    res = sb.table("user_usage").select("*").eq("email", email_n).execute()
    rows = res.data or []
    if rows:
        return rows[0]

    # Create a new usage row (free plan by default)
    insert = {
        "email": email_n,
        "plan": "free",
        "monthly_quota": FREE_QUOTA,
        "searches_used": 0,
        "last_reset": today().isoformat(),
    }
    sb.table("user_usage").insert(insert).execute()
    return insert


def resolve_quota(plan: str, explicit_quota: Optional[int]) -> int:
    if explicit_quota and explicit_quota > 0:
        return int(explicit_quota)
    if (plan or "").lower() == "pro":
        return PRO_QUOTA
    return FREE_QUOTA


def ensure_monthly_reset(usage: dict) -> dict:
    """If last_reset < start_of_this_month, reset counters."""
    last_reset_val = usage.get("last_reset")
    needs_reset = False
    try:
        if not last_reset_val:
            needs_reset = True
        else:
            # last_reset is date (YYYY-MM-DD) from Supabase
            lr = dt.date.fromisoformat(str(last_reset_val)[0:10])
            if lr < start_of_this_month():
                needs_reset = True
    except Exception:
        needs_reset = True

    if needs_reset:
        upd = {
            "searches_used": 0,
            "last_reset": today().isoformat()
        }
        sb.table("user_usage").update(upd).eq("email", usage["email"]).execute()
        usage.update(upd)
    return usage


def increment_usage(email: str):
    sb.table("user_usage") \
      .update({"searches_used": sb.rpc("increment", {"x": 1}) if hasattr(sb, "rpc") else None})  # fallback below if no rpc
    # Simple safe update without rpc:
    res = sb.table("user_usage").select("searches_used").eq("email", email).execute()
    used = (res.data or [{}])[0].get("searches_used", 0)
    sb.table("user_usage").update({"searches_used": used + 1}).eq("email", email).execute()


# -----------------------------
# Search logic
# -----------------------------
def run_search(term: str, limit: int = 20) -> list:
    """
    Query your 'tenders' table by title (and fallback buyer::text).
    Only uses columns you already have.
    """
    term_like = f"%{term}%"
    # First try against title
    try:
        res = (
            sb.table("tenders")
              .select("title, buyer, published_date, value_text, notice_url")
              .ilike("title", term_like)
              .limit(limit)
              .execute()
        )
        data = res.data or []
        if data:
            return data
    except Exception:
        pass

    # Fallback: try buyer::text if supported by PostgREST filter -> cast jsonb to text by ->> ?
    # Many PostgREST setups expose jsonb as text for ilike; if not, this just returns empty.
    try:
        res2 = (
            sb.table("tenders")
              .select("title, buyer, published_date, value_text, notice_url")
              .ilike("buyer", term_like)
              .limit(limit)
              .execute()
        )
        return res2.data or []
    except Exception:
        return []


def log_search(email: str):
    """
    Insert one row into search_logs.
    Your table has (id uuid, email text, search_at timestamptz default now()).
    """
    try:
        sb.table("search_logs").insert({"email": email}).execute()
    except Exception:
        # Non-blocking
        pass


# -----------------------------
# Main app after auth
# -----------------------------
def app_home(email: str):
    st.title(APP_TITLE)

    # Usage box on the left
    usage = fetch_or_create_usage(email)
    usage = ensure_monthly_reset(usage)

    plan = (usage.get("plan") or "free").lower()
    monthly_quota = resolve_quota(plan, usage.get("monthly_quota"))
    used = int(usage.get("searches_used") or 0)

    with st.sidebar:
        st.write(f"Logged in as\n**{email}**")
        st.write(f"**Plan:** {plan.capitalize()}")
        st.write(f"**Searches used:** {used}/{monthly_quota}")
        if st.button("Logout", use_container_width=True):
            try:
                sb.auth.sign_out()
            except Exception:
                pass
            st.session_state.pop("logged_in_email", None)
            st.success("Logged out.")
            st.rerun()

    st.caption("Find public **cleaning tenders** faster and smarter — free for your first 5 searches each month.")

    term = st.text_input("Describe what you're looking for", placeholder="e.g. NHS cleaning tenders in UK")
    if st.button("Search", type="primary", disabled=not term.strip()):
        # Enforce quota
        if used >= monthly_quota:
            st.error("You’ve reached your monthly search limit for your plan. Upgrade to Pro to unlock more.")
            return

        # Do the search
        with st.spinner("Searching…"):
            data = run_search(term.strip(), limit=20)

        # Update usage + log
        increment_usage(email)
        log_search(email)

        # Refresh usage for sidebar
        usage = fetch_or_create_usage(email)
        used = int(usage.get("searches_used") or 0)
        st.experimental_set_query_params(_=dt.datetime.utcnow().timestamp())  # minor cache-bust for Cloud

        # Show results
        st.success(f"Search recorded ✅ ({used}/{monthly_quota})")
        if not data:
            st.info("No tenders matched. Try a broader term.")
        else:
            for row in data:
                title = row.get("title") or "(Untitled tender)"
                buyer = row.get("buyer")
                try:
                    # buyer is jsonb; render as string safely
                    buyer_txt = buyer if isinstance(buyer, str) else str(buyer)
                except Exception:
                    buyer_txt = ""
                published = row.get("published_date")
                val_txt = row.get("value_text")
                notice_url = row.get("notice_url")

                with st.container(border=True):
                    st.markdown(f"**{title}**")
                    if buyer_txt and buyer_txt != "EMPTY":
                        st.write(buyer_txt)
                    meta_bits = []
                    if published:
                        meta_bits.append(f"Published: {str(published)[:10]}")
                    if val_txt and val_txt != "NULL":
                        meta_bits.append(f"Value: {val_txt}")
                    if meta_bits:
                        st.caption(" • ".join(meta_bits))
                    if notice_url and notice_url != "EMPTY":
                        st.link_button("Open notice", notice_url, use_container_width=False)


# -----------------------------
# Entry
# -----------------------------
def main():
    st.set_page_config(page_title="CleanIntel", layout="wide")
    if "logged_in_email" not in st.session_state:
        # Try get current user from Supabase (useful after email confirm + redirect)
        try:
            user = sb.auth.get_user()
            if user and getattr(user, "user", None) and getattr(user.user, "email", None):
                st.session_state["logged_in_email"] = normalize_email(user.user.email)
        except Exception:
            pass

    email = st.session_state.get("logged_in_email")
    if not email:
        st.title(APP_TITLE)
        auth_screen()
        return

    app_home(email)


if __name__ == "__main__":
    main()
