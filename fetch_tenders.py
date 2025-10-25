import os
import requests
import pandas as pd
from datetime import datetime, timezone
from supabase import create_client
from dotenv import load_dotenv

# ----------------------------------------------------------
# 1. Load environment variables
# ----------------------------------------------------------
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ----------------------------------------------------------
# 2. Helper functions
# ----------------------------------------------------------
def detect_region(text):
    """Simple keyword-based region detection."""
    if not text or not isinstance(text, str):
        return None
    text_lower = text.lower()
    if any(x in text_lower for x in ["london", "westminster", "croydon"]):
        return "London"
    elif any(x in text_lower for x in ["scotland", "edinburgh", "glasgow"]):
        return "Scotland"
    elif any(x in text_lower for x in ["birmingham", "manchester", "leeds", "liverpool", "yorkshire", "midlands"]):
        return "Midlands & North"
    elif any(x in text_lower for x in ["bristol", "southampton", "oxford", "cambridge", "kent", "sussex"]):
        return "South England"
    elif "wales" in text_lower:
        return "Wales"
    elif "northern ireland" in text_lower or "belfast" in text_lower:
        return "Northern Ireland"
    else:
        return "UK (General)"


def detect_sector(text):
    """Classify sector based on title or description."""
    if not text or not isinstance(text, str):
        return None
    text_lower = text.lower()
    if any(x in text_lower for x in ["software", "it", "technology", "digital"]):
        return "Information Technology"
    elif any(x in text_lower for x in ["cleaning", "janitorial", "maintenance", "facilities"]):
        return "Facilities & Cleaning"
    elif any(x in text_lower for x in ["construction", "building", "engineering", "civil"]):
        return "Construction & Engineering"
    elif any(x in text_lower for x in ["health", "hospital", "nhs", "medical"]):
        return "Healthcare"
    elif any(x in text_lower for x in ["education", "school", "university", "college"]):
        return "Education"
    elif any(x in text_lower for x in ["transport", "rail", "bus", "airport", "road"]):
        return "Transport & Infrastructure"
    else:
        return "General Public Sector"


# ----------------------------------------------------------
# 3. Fetch tenders from Contracts Finder API
# ----------------------------------------------------------
def fetch_latest_tenders(limit=50):
    print("🚀 Fetching tenders from Contracts Finder API...")

    headers = {"Accept": "application/json"}
    params = {
        "limit": limit,
        "order": "desc",
        "orderBy": "publicationDate",
        "status": "open",
        "showExpired": "false"
    }

    response = requests.get(
        "https://www.contractsfinder.service.gov.uk/Published/Notices/OCDS/Search",
        headers=headers,
        params=params
    )

    if response.status_code != 200:
        print(f"❌ HTTP Error {response.status_code}: {response.text[:300]}")
        return pd.DataFrame()

    try:
        data = response.json()
    except Exception as e:
        print("❌ Failed to parse JSON:", e)
        print(response.text[:400])
        return pd.DataFrame()

    # Flexible extraction
    if "records" in data:
        notices = data["records"]
    elif "releases" in data:
        notices = data["releases"]
    else:
        print("⚠️ No 'records' or 'releases' key found in API response.")
        print(f"Keys returned: {list(data.keys())}")
        return pd.DataFrame()

    print(f"Fetched {len(notices)} tenders from API.")

    tenders = []
    for n in notices[:limit]:
        release = n.get("releases", [n])[0]
        tender_info = release.get("tender", {})

        title = tender_info.get("title", "No title")
        desc = tender_info.get("description", "")
        published = release.get("date", None)
        deadline = tender_info.get("tenderPeriod", {}).get("endDate", None)
        value = tender_info.get("value", {})
        value_amount = value.get("amount")
        currency = value.get("currency", "GBP")

        tender = {
            "tender_id": release.get("ocid"),
            "title": title,
            "description": desc,
            "published_date": published,
            "deadline": deadline,
            "value_gbp": float(value_amount) if value_amount else 0,
            "currency": currency,
            "region": detect_region(title + " " + desc),
            "sector": detect_sector(title + " " + desc),
            "tender_status": tender_info.get("status", "Open"),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        tenders.append(tender)

    print(f"✅ Parsed {len(tenders)} valid tenders.")
    return pd.DataFrame(tenders)


# ----------------------------------------------------------
# 4. Upload to Supabase (UPSERT)
# ----------------------------------------------------------
def insert_into_supabase(df):
    print(f"Inserting {len(df)} tenders into Supabase...")
    success, fail = 0, 0

    for _, row in df.iterrows():
        record = row.to_dict()
        record.pop("id", None)  # ✅ Prevents 'id' conflicts with Supabase identity column
        try:
            supabase.table("tenders").upsert(
                record,
                on_conflict="tender_id"  # ✅ ensures update instead of duplicate insert
            ).execute()
            success += 1
        except Exception as e:
            fail += 1
            print(f"⚠️ Error inserting {record.get('tender_id')}: {e}")

    print(f"✅ Successfully inserted/updated {success} tenders; ❌ failed {fail}")


# ----------------------------------------------------------
# 5. Main entry point
# ----------------------------------------------------------
def main():
    df = fetch_latest_tenders(limit=50)
    if df.empty:
        print("⚠️ No tenders fetched.")
        return
    insert_into_supabase(df)
    print("✅ All tenders inserted successfully!")


if __name__ == "__main__":
    main()
