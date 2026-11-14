import os
import re
import requests
from datetime import datetime, timedelta, timezone

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
TABLE = "pending_deploys"
EXPIRY_HOURS = 24
_UUID = re.compile(r"^[0-9a-fA-F-]{36}$")


def _headers(extra=None):
    h = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }
    if extra:
        h.update(extra)
    return h


def _url(query=""):
    return f"{SUPABASE_URL}/rest/v1/{TABLE}{query}"


def _check_id(dep_id):
    if not isinstance(dep_id, str) or not _UUID.match(dep_id):
        raise ValueError("invalid id")
    return dep_id


def create(code, prompt, filename, task, difficulty, provider, source="deploy"):
    row = {
        "status": "pending", "source": source, "code": code, "prompt": prompt,
        "filename": filename, "task": task, "difficulty": difficulty, "provider": provider,
    }
    r = requests.post(_url(), headers=_headers({"Prefer": "return=representation"}),
                      json=row, timeout=10)
    r.raise_for_status()
    return r.json()[0]


def list_pending(limit=20):
    q = f"?status=eq.pending&order=created_at.desc&limit={int(limit)}"
    r = requests.get(_url(q), headers=_headers(), timeout=10)
    r.raise_for_status()
    return r.json()


def claim(dep_id, new_status="approved"):
    """Atomically move a pending row to new_status. Returns the row, or None if it
    was not pending, was already decided, or is older than EXPIRY_HOURS."""
    _check_id(dep_id)
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=EXPIRY_HOURS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    q = f"?id=eq.{dep_id}&status=eq.pending&created_at=gte.{cutoff}"
    body = {"status": new_status, "decided_at": datetime.now(timezone.utc).isoformat()}
    r = requests.patch(_url(q), headers=_headers({"Prefer": "return=representation"}),
                       json=body, timeout=10)
    r.raise_for_status()
    rows = r.json()
    return rows[0] if rows else None


def update(dep_id, fields):
    _check_id(dep_id)
    r = requests.patch(_url(f"?id=eq.{dep_id}"), headers=_headers(), json=fields, timeout=10)
    r.raise_for_status()
