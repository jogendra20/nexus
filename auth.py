import os
from flask import request, jsonify

NEXUS_SECRET = os.getenv("NEXUS_SECRET") or os.getenv("NEXUS_API_KEY")

def auth_required():
    key = request.headers.get("X-API-Key")
    if not key:
        data = request.get_json(silent=True) or {}
        key = data.get("api_key")
    return bool(NEXUS_SECRET) and key == NEXUS_SECRET
