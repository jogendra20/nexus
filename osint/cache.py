import os
import json
import urllib.request as ur
from datetime import datetime, timezone

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

# TTL in seconds per type
TTL = {
    "ip":       3600,    # 1 hour
    "phone":    86400,   # 24 hours
    "domain":   21600,   # 6 hours
    "company":  43200,   # 12 hours
    "username": 86400,   # 24 hours
}

def _headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }

def get_cached(query_type: str, query: str):
    if not SUPABASE_URL:
        return None
    try:
        import urllib.parse
        q = urllib.parse.quote(query)
        url = (
            f"{SUPABASE_URL}/rest/v1/osint_cache"
            f"?query_type=eq.{query_type}&query=eq.{q}"
            f"&select=result,expires_at&limit=1"
        )
        req = ur.Request(url, headers=_headers())
        res = ur.urlopen(req, timeout=15)
        rows = json.loads(res.read())
        if not rows:
            return None
        row = rows[0]
        # Check expiry
        expires_at = datetime.fromisoformat(row["expires_at"].replace("Z", "+00:00"))
        if datetime.now(timezone.utc) > expires_at:
            return None
        return row["result"]
    except Exception as e:
        print(f"[OSINT Cache] get error: {e}")
        return None

def set_cache(query_type: str, query: str, result: dict):
    if not SUPABASE_URL:
        return
    try:
        from datetime import timedelta
        ttl_seconds = TTL.get(query_type, 3600)
        expires_at = (datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)).isoformat()
        payload = json.dumps({
            "query_type": query_type,
            "query": query,
            "result": result,
            "expires_at": expires_at,
        }).encode()
        req = ur.Request(
            f"{SUPABASE_URL}/rest/v1/osint_cache",
            data=payload,
            headers={**_headers(), "Prefer": "resolution=merge-duplicates"},
            method="POST"
        )
        ur.urlopen(req, timeout=15)
    except Exception as e:
        print(f"[OSINT Cache] set error: {e}")
