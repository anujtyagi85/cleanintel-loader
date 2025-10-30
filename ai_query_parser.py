# ai_query_parser.py
import os
import re
import json
from openai import OpenAI

# Initialize new OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def parse_ai_prompt(prompt: str):
    """
    Uses GPT to turn natural language queries into structured filter instructions.
    Returns a dict with: region, sector, value_cap, timeframe_days
    """
    if not prompt or len(prompt.strip()) == 0:
        return {}

    system_prompt = """You are a data parser for tender search queries.
    Extract region, sector, max tender value in GBP, and timeframe (days until deadline).
    Return JSON like:
    {"region": "London", "sector": "cleaning", "value_cap": 2000000, "timeframe_days": 30}
    If not specified, leave fields null.
    """

    # ✅ Modern API call
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        temperature=0,
    )

    text = response.choices[0].message.content
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        return {}
    try:
        return json.loads(match.group(0))
    except Exception:
        return {}
