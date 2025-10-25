import os
import pandas as pd
import streamlit as st
from supabase import create_client
from dotenv import load_dotenv
from datetime import datetime, timezone

# ----------------------------------------------------------
# 1. Load environment variables and connect to Supabase
# ----------------------------------------------------------
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ----------------------------------------------------------
# 2. Streamlit Page Config
# ----------------------------------------------------------
st.set_page_config(
    page_title="Cleanintel | Tender Intelligence Dashboard",
    page_icon="🧠",
    layout="wide"
)

# ----------------------------------------------------------
# 3. Fetch tenders data safely
# ----------------------------------------------------------
@st.cache_data(ttl=600)
def load_tenders():
    response = supabase.table("tenders").select("*").execute()
    data = response.data
    df = pd.DataFrame(data)

    if not df.empty:
        # Handle timestamps safely
        df["published_date"] = pd.to_datetime(df["published_date"], errors="coerce")
        df["deadline"] = pd.to_datetime(df["deadline"], errors="coerce")

        # Ensure timezone-aware for consistent subtraction
        df["deadline"] = df["deadline"].apply(
            lambda x: x.tz_localize("UTC") if pd.notnull(x) and x.tzinfo is None else x
        )

        now_utc = pd.Timestamp.now(tz="UTC")

        # Calculate days remaining safely
        df["days_remaining"] = df["deadline"].apply(
            lambda x: (x - now_utc).days if pd.notnull(x) else None
        )

        # Normalize numeric values
        df["value_gbp"] = pd.to_numeric(df["value_gbp"], errors="coerce").fillna(0)

        # Sort by published date (latest first)
        df = df.sort_values(by="published_date", ascending=False)

    return df


df = load_tenders()

# ----------------------------------------------------------
# 4. Sidebar Filters
# ----------------------------------------------------------
st.sidebar.header("🔍 Filters")

if df.empty:
    st.warning("No tender data available. Please run the fetch script first.")
    st.stop()

regions = sorted(df["region"].dropna().unique().tolist())
sectors = sorted(df["sector"].dropna().unique().tolist())
statuses = sorted(df["tender_status"].dropna().unique().tolist())

selected_region = st.sidebar.multiselect("Region", regions)
selected_sector = st.sidebar.multiselect("Sector", sectors)
selected_status = st.sidebar.multiselect("Tender Status", statuses)

min_val, max_val = int(df["value_gbp"].min()), int(df["value_gbp"].max())
selected_val = st.sidebar.slider("Value Range (GBP)", min_val, max_val, (min_val, max_val))

# Apply filters
filtered_df = df.copy()
if selected_region:
    filtered_df = filtered_df[filtered_df["region"].isin(selected_region)]
if selected_sector:
    filtered_df = filtered_df[filtered_df["sector"].isin(selected_sector)]
if selected_status:
    filtered_df = filtered_df[filtered_df["tender_status"].isin(selected_status)]
filtered_df = filtered_df[
    (filtered_df["value_gbp"] >= selected_val[0]) & (filtered_df["value_gbp"] <= selected_val[1])
]

# ----------------------------------------------------------
# 5. KPIs Section
# ----------------------------------------------------------
st.title("🧠 Cleanintel Tender Intelligence Dashboard")
st.caption("Real-time tender intelligence powered by Supabase")

total_tenders = len(filtered_df)
total_value = filtered_df["value_gbp"].sum()
avg_value = filtered_df["value_gbp"].mean() if total_tenders > 0 else 0

col1, col2, col3 = st.columns(3)
col1.metric("📊 Total Tenders", f"{total_tenders}")
col2.metric("💷 Total Value (GBP)", f"£{total_value:,.0f}")
col3.metric("🧾 Avg Tender Value", f"£{avg_value:,.0f}")

st.markdown("---")

# ----------------------------------------------------------
# 6. Charts
# ----------------------------------------------------------
st.subheader("📍 Tenders by Region")
region_summary = filtered_df.groupby("region")["value_gbp"].sum().reset_index()
if not region_summary.empty:
    st.bar_chart(region_summary, x="region", y="value_gbp", use_container_width=True)
else:
    st.info("No data available for selected filters.")

st.subheader("🏗️ Tenders by Sector")
sector_summary = filtered_df.groupby("sector")["value_gbp"].sum().reset_index()
if not sector_summary.empty:
    st.bar_chart(sector_summary, x="sector", y="value_gbp", use_container_width=True)
else:
    st.info("No data available for selected filters.")

st.markdown("---")

# ----------------------------------------------------------
# 7. Upcoming Deadlines (Next 30 Days)
# ----------------------------------------------------------
st.subheader("📅 Upcoming Deadlines (Next 30 Days)")
upcoming = filtered_df[filtered_df["days_remaining"].between(0, 30, inclusive="both")]
upcoming = upcoming.sort_values("deadline", ascending=True)

if not upcoming.empty:
    st.dataframe(
        upcoming[["title", "region", "sector", "value_gbp", "deadline", "days_remaining"]],
        use_container_width=True,
        hide_index=True
    )
else:
    st.info("No tenders closing in the next 30 days.")

st.markdown("---")

# ----------------------------------------------------------
# 8. Footer
# ----------------------------------------------------------
st.caption("💡 Cleanintel | Built with Streamlit + Supabase | v1.0.1")
