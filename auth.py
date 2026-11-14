import hmac
import os
from flask import request


def _keys():
    raw = os.getenv("NEXUS_SECRET") or os.getenv("NEXUS_API_KEY") or ""
    return [k.strip() for k in raw.split(",") if k.strip()]


def auth_required():
    key = request.headers.get("X-API-Key")
    if not key:
        data = request.get_json(silent=True) or {}
        key = data.get("api_key")
    if not key:
        return False
    return any(hmac.compare_digest(key.encode(), k.encode()) for k in _keys())
