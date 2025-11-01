import os, time
import requests
from datetime import datetime
from urllib.parse import urlencode
from supabase import create_client, Client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]

sb: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

BASE = "https://www.contractsfinder.service.gov.uk/Published/Notices/OCDS/Search"


def _get(d, *path, default=None):
    for p in path:
        if not isinstance(d, dict):
            return default
        d = d.get(p)
        if d is None:
            return default
    return d


def fetch_page(page: int, page_size: int = 50) -> dict:
    params = {
        "order": "desc",
        "sortType": "publishedDate",
        "page": page,
        "pageSize": page_size,
        "status": "Open",
        "type": "Opportunity"
    }
    url = f"{BASE}?{urlencode(params)}"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.json()


def normalize(row: dict) -> dict:
    tender_id = _get(row, "id") or _get(row, "ocid")

    title = (_get(row, "title") or "").strip()
    description = _get(row, "description")

    published_raw = _get(row, "publishedDate")
    published_date = None
    if published_raw:
        try:
            published_date = datetime.fromisoformat(published_raw.replace("Z", "+00:00"))
        except:
            published_date = None

    buyer = {
        "name": _get(row, "buyer", "name"),
        "id": _get(row, "buyer", "id"),
        "contactPoint": _get(row, "buyer", "contactPoint")
    }

    val = _get(row, "value")
    value_normalized = None
    if isinstance(val, dict):
        value_normalized = val.get("amount")

    sector = _get(row, "mainProcurementCategory")

    return {
        "tender_id": tender_id,
        "title": title,
        "description": description,
        "buyer": buyer,
        "sector": sector,
        "value_normalized": value_normalized,
        "published_date": published_date.isoformat() if published_date else None,
    }


def upsert_rows(rows):
    if rows:
        sb.table("tenders").upsert(rows, on_conflict="tender_id").execute()


def main():
    page = 1
    total_inserted = 0

    while True:
        data = fetch_page(page)
        records = data.get("records") or data.get("items") or []
        if not records:
            break

        processed = [normalize(r) for r in records if r]
        processed = [p for p in processed if p.get("title")]

        upsert_rows(processed)
        total_inserted += len(processed)

        total_pages = data.get("totalPages", 0)
        if total_pages and page >= total_pages:
            break

        page += 1
        time.sleep(0.4)

    print(f"Done. Inserted / updated: {total_inserted} tenders.")


if __name__ == "__main__":
    main()
