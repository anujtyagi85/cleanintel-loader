import os
from supabase import create_client as create_supabase_client
from dotenv import load_dotenv

# load .env automatically when this file is imported
load_dotenv()

def create_client():
    """
    Returns a ready-to-use Supabase client by reading
    SUPABASE_URL and SUPABASE_KEY from the .env file.
    """
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")

    if not url or not key:
        raise ValueError("Missing SUPABASE_URL or SUPABASE_KEY in .env")

    return create_supabase_client(url, key)
