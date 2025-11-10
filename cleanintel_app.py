# cleanintel_app.py
import os
import json
import pandas as pd
import streamlit as st
from supabase import create_client

st.set_page_config(page_title="CleanIntel – UK Tender Intelligence", page_icon="🧽", layout="wide")
st.title("CleanIntel – UK Tender Intelligence")
st.write("Fuzzy search in title, fallback to buyer (JSON stored).")

# --- Read secrets robustly (env first, then st.secrets) ---
def read_secret(name: str) -> str | None:
    val = os.getenv(name)
    if val:
        return val.strip()
    try:
        return st.secrets.get(name, "").strip()
    except Exception:
        return None

SUPABASE_URL = read_secret("SUPABASE_URL")
SUPABASE_KEY = read_secret("SUPABASE_KEY")

# --- Validate secrets early and show actionable hints ---
def mask_key(k: str) -> str:
    if not k:
        return ""
    if len(k) <= 12:
        return "***"
    return f"{k[:6]}...{k[-6:]}"

problems: list[str] = []
if not SUPABASE_URL:
    problems.append("`SUPABASE_URL` is missing.")
else:
    if not SUPABASE_URL.startswith("http"):
        problems.append("`SUPABASE_URL` must start with `https://` (copy it exactly from Supabase).")
    if ".supabase.co" not in SUPABASE_URL:
        problems.append("`SUPABASE_URL` should contain `.supabase.co`.")

if not SUPABASE_KEY:
    problems.append("`SUPABASE_KEY` is missing.")

if problems:
    st.error("Configuration error:\n\n- " + "\n- ".join(problems))
    st.info(
        "Open **Manage app → App settings → Secrets** and set exactly:\n\n"
        '```\n'
        'SUPABASE_URL="https://myohjatisjbalthdbwku.supabase.co"\n'
        'SUPABASE_KEY="<your long service role key>"\n'
        '```\n'
        "Save, wait ~30–60 seconds, then click **Rerun** in Streamlit."
    )
    st.caption(
        f"Current detected: URL={SUPABASE_URL or '❌ missing'} | KEY={mask_key(SUPABASE_KEY) or '❌ missing'}"
    )
    st.stop()

# --- Create client (will raise if URL is bad and produce Errno -2 otherwise) ---
try:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error(f"Failed to initialize Supabase client: {e}")
    st.caption(f"URL seen: {SUPABASE_URL}")
    st.stop()

keyword = st.text_input("Keyword (e.g., cleaning, school, waste, solar)")

if keyword:
    try:
        # OR across title and buyer (jsonb cast to text)
        query = (
            supabase.table("tenders")
            .select("title, buyer, value_gbp, status, deadline")
            .or_(f"title.ilike.%{keyword}%,buyer::text.ilike.%{keyword}%")
            .limit(200)
        )
        response = query.execute()
        rows = response.data or []

        if not rows:
            st.warning("No tenders found.")
            st.stop()

        df = pd.DataFrame(rows)

        # buyer json → readable string (simple view). We’ll improve later if needed.
        if "buyer" in df.columns:
            # If jsonb is a dict → pick a few common paths; else stringify.
            def extract_name(obj):
                if isinstance(obj, dict):
                    if obj.get("name"):
                        return obj["name"]
                    cp = obj.get("contactPoint")
                    if isinstance(cp, dict) and cp.get("name"):
                        return cp["name"]
                    org = obj.get("organization")
                    if isinstance(org, dict) and org.get("name"):
                        return org["name"]
                # jsonb as a plain string (e.g., "Royal Hospital Chelsea")
                if isinstance(obj, str):
                    return obj.strip('"')
                # fallback
                try:
                    return json.dumps(obj, ensure_ascii=False)
                except Exception:
                    return str(obj)

            df["buyer_name"] = df["buyer"].apply(extract_name)
        else:
            df["buyer_name"] = None

        # final order
        keep = [c for c in ["title", "buyer_name", "value_gbp", "status", "deadline"] if c in df.columns]
        df = df[keep]

        st.success(f"Found {len(df)} tenders")
        st.dataframe(df, use_container_width=True)
    except Exception as e:
        st.error(f"Query failed: {e}")
else:
    st.info("Search tenders above to begin.")
