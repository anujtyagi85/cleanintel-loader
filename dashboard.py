import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from supabase import create_client
import plotly.express as px

# -----------------------
# Load Supabase connection
# -----------------------
import os

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# -----------------------
# Streamlit Page Settings
# -----------------------
st.set_page_config(
    page_title="CleanIntel Dashboard",
    page_icon="🧠",
    layout="wide",
)

# Custom CSS for Figma-like UI
st.markdown("""
    <style>
    body {
        background-color: #fafafa;
    }
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        padding-left: 3rem;
        padding-right: 3rem;
    }
    h1, h2, h3, h4 {
        font-family: 'Inter', sans-serif;
        color: #333333;
    }
    .metric-card {
        background-color: white;
        border-radius: 16px;
        padding: 20px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05);
        text-align: center;
    }
    .region-chart {
        background-color: white;
        border-radius: 16px;
        padding: 20px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05);
    }
    .data-table {
        background-color: white;
        border-radius: 16px;
        padding: 20px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05);
    }
    </style>
""", unsafe_allow_html=True)

# -----------------------
# Fetch Data
# -----------------------
@st.cache_data(ttl=600)
def load_tenders():
    response = supabase.table("tenders").select("*").execute()
    df = pd.DataFrame(response.data)
    if df.empty:
        return df

    df["deadline"] = pd.to_datetime(df["deadline"], errors="coerce", utc=True)
    df["days_remaining"] = (df["deadline"] - datetime.now(timezone.utc)).dt.days
    df["value_gbp"] = pd.to_numeric(df["value_gbp"], errors="coerce").fillna(0)
    return df

df = load_tenders()

# -----------------------
# Sidebar Filters
# -----------------------
with st.sidebar:
    st.markdown("## 🔍 Filters")
    selected_region = st.multiselect("Region", sorted(df["region"].dropna().unique()))
    selected_sector = st.multiselect("Sector", sorted(df["sector"].dropna().unique()))
    selected_status = st.multiselect("Tender Status", sorted(df["tender_status"].dropna().unique()))
    value_range = st.slider("Value Range (GBP)", 0, int(df["value_gbp"].max()), (0, int(df["value_gbp"].max())))

# -----------------------
# Apply Filters
# -----------------------
if not df.empty:
    filtered = df[
        ((df["region"].isin(selected_region)) | (not selected_region)) &
        ((df["sector"].isin(selected_sector)) | (not selected_sector)) &
        ((df["tender_status"].isin(selected_status)) | (not selected_status)) &
        (df["value_gbp"].between(value_range[0], value_range[1]))
    ]
else:
    filtered = df

# -----------------------
# Header
# -----------------------
st.markdown("### 🧠 **CleanIntel Tender Intelligence Dashboard**")
st.markdown("_Real-time tender intelligence powered by Supabase_")

# -----------------------
# Metrics Section
# -----------------------
col1, col2, col3 = st.columns(3)
with col1:
    st.markdown('<div class="metric-card">📊 <h3>Total Tenders</h3><h2>' + str(len(filtered)) + '</h2></div>', unsafe_allow_html=True)
with col2:
    st.markdown('<div class="metric-card">💷 <h3>Total Value (GBP)</h3><h2>£' + f"{filtered['value_gbp'].sum():,.0f}" + '</h2></div>', unsafe_allow_html=True)
with col3:
    avg_value = filtered["value_gbp"].mean() if len(filtered) > 0 else 0
    st.markdown('<div class="metric-card">📈 <h3>Avg Tender Value</h3><h2>£' + f"{avg_value:,.0f}" + '</h2></div>', unsafe_allow_html=True)

# -----------------------
# Charts
# -----------------------
if not filtered.empty:
    region_group = filtered.groupby("region")["value_gbp"].sum().reset_index()
    with st.container():
        st.markdown("### 📍 Tenders by Region")
        fig = px.bar(region_group, x="region", y="value_gbp", color="region",
                     title="", text_auto='.2s', color_discrete_sequence=px.colors.qualitative.Set2)
        fig.update_layout(
            showlegend=False,
            height=400,
            plot_bgcolor="white",
            paper_bgcolor="white",
            xaxis_title="Region",
            yaxis_title="Value (£)",
            font=dict(size=13)
        )
        st.plotly_chart(fig, use_container_width=True)

# -----------------------
# Upcoming Deadlines
# -----------------------
st.markdown("### 🗓️ Upcoming Deadlines (Next 30 Days)")
upcoming = filtered[(filtered["days_remaining"] >= 0) & (filtered["days_remaining"] <= 30)].sort_values("deadline")
st.dataframe(
    upcoming[["title", "region", "sector", "value_gbp", "deadline", "days_remaining"]],
    use_container_width=True,
    hide_index=True
)

# -----------------------
# Footer
# -----------------------
st.markdown("---")
st.caption("💡 CleanIntel | Built with Streamlit + Supabase | v1.1 (Figma UI Edition)")
