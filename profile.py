import os
import json
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")


def get_profile() -> dict:
    """Fetch all profile keys from Supabase."""
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/user_profile?select=key,value,category",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}"
        }
    )
    try:
        res = urllib.request.urlopen(req, timeout=8)
        rows = json.loads(res.read())
        return {r["key"]: r["value"] for r in rows}
    except Exception as e:
        print(f"[Profile] fetch failed: {e}")
        return {}


def update_profile(key: str, value: str, category: str = "personal"):
    """Update or insert a profile key."""
    payload = json.dumps({
        "key": key,
        "value": value,
        "category": category,
        "updated_at": datetime.now().isoformat()
    }).encode()

    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/user_profile",
        data=payload,
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates"
        },
        method="POST"
    )
    try:
        urllib.request.urlopen(req, timeout=8)
        return True
    except Exception as e:
        print(f"[Profile] update failed: {e}")
        return False


def get_context_string() -> str:
    """Return a compressed context string to inject into LLM prompts."""
    profile = get_profile()
    if not profile:
        return ""

    now = datetime.now(ZoneInfo("Asia/Kolkata"))
    day = now.strftime("%A")
    time_str = now.strftime("%H:%M")
    date_str = now.strftime("%d %B %Y")

    trading_days = profile.get("trading_days", "").split(",")
    gym_days = profile.get("gym_days", "").split(",")
    is_trading_day = day in trading_days
    is_gym_day = day in gym_days
    market_open = profile.get("market_open", "09:15")
    market_close = profile.get("market_close", "15:30")
    market_hours = f"{market_open}–{market_close} IST"
    market_status = "OPEN" if (
        is_trading_day and
        market_open <= time_str <= market_close
    ) else "CLOSED"

    context = f"""[NEXUS CONTEXT]
User: {profile.get('name', 'User')}
Date: {date_str} ({day}) | Time: {time_str} IST
Goal: {profile.get('goal', '')}
Market: {market_status} ({market_hours})
Trading day: {is_trading_day} | Gym day: {is_gym_day}
College day: {day in profile.get('college_days', '').split(',')}
[/NEXUS CONTEXT]"""

    return context
