import os
from flask import request, jsonify

NEXUS_SECRET = os.getenv("NEXUS_SECRET", "changeme")

def auth_required():
    key = request.headers.get("X-API-Key")
    if not key:
        data = request.get_json(silent=True) or {}
        key = data.get("api_key")
    return key == NEXUS_SECRET
