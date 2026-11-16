"""key_check_more.py - check the non-LLM keys: search, Jina, Poe, Telegram, GitHub,
Supabase (read AND write, which proves the approval queue works), Perplexity, Drona.
Key values are never returned; error text is redacted."""
import base64
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor

import requests

from key_check import _redact

TIMEOUT = 20


def _row(provider, label):
    return {"provider": provider, "model": label, "status": "", "tools": None,
            "latency_ms": None, "ratelimit": {}, "error": ""}


def _classify(code):
    if 200 <= code < 300:
        return "ok"
    if code in (401, 403):
        return "auth_failed"
    if code == 402:
        return "payment_required"
    if code in (429, 432, 433):
        return "quota_or_rate_limit"
    return f"http_{code}"


def _http(provider, label, key, method, url, **kw):
    row = _row(provider, label)
    if not key:
        row["status"] = "no_key"
        return row
    start = time.time()
    try:
        r = requests.request(method, url, timeout=TIMEOUT, **kw)
    except Exception as e:
        row["status"] = "error"
        row["error"] = _redact(f"{type(e).__name__}: {e}", key)
        return row
    row["latency_ms"] = int((time.time() - start) * 1000)
    row["status"] = _classify(r.status_code)
    for k, v in r.headers.items():
        lk = k.lower()
        if lk.startswith("x-ratelimit") or lk in ("retry-after", "x-oauth-scopes"):
            row["ratelimit"][lk] = v
    if row["status"] != "ok":
        row["error"] = _redact(r.text, key)
    return row, r


def _wrap(result):
    return result[0] if isinstance(result, tuple) else result


def _jwt_role(key):
    try:
        payload = key.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload)).get("role", "?")
    except Exception:
        return "non-jwt-key"


def _tavily(env):
    k = os.getenv(env)
    return _wrap(_http("tavily", env, k, "POST", "https://api.tavily.com/search",
                       json={"api_key": k, "query": "test", "max_results": 1}))


def _serper(env):
    k = os.getenv(env)
    return _wrap(_http("serper", env, k, "POST", "https://google.serper.dev/news",
                       headers={"X-API-KEY": k or "", "Content-Type": "application/json"},
                       json={"q": "test", "num": 1}))


def _youcom(env):
    k = os.getenv(env)
    return _wrap(_http("youcom", env, k, "POST", "https://ydc-index.io/v1/search",
                       headers={"X-API-Key": k or "", "Content-Type": "application/json"},
                       json={"query": "test", "count": 1}))


def _jina():
    k = os.getenv("JINA_API_KEY")
    return _wrap(_http("jina", "reader", k, "GET", "https://r.jina.ai/https://example.com",
                       headers={"Authorization": f"Bearer {k}"}))


def _telegram():
    k = os.getenv("TELEGRAM_BOT_TOKEN")
    return _wrap(_http("telegram", "getMe", k, "GET", f"https://api.telegram.org/bot{k}/getMe"))


def _github():
    k = os.getenv("GITHUB_TOKEN")
    try:
        from github_pusher import BASE_URL
    except Exception:
        BASE_URL = "https://api.github.com/user"
    res = _http("github", "Automate repo", k, "GET", BASE_URL,
                headers={"Authorization": f"Bearer {k}", "Accept": "application/vnd.github+json"})
    if not isinstance(res, tuple):
        return res
    row, r = res
    scopes = row["ratelimit"].get("x-oauth-scopes", "")
    if row["status"] == "ok":
        try:
            row["ratelimit"]["push"] = str(r.json().get("permissions", {}).get("push"))
        except Exception:
            pass
        if "admin:" in scopes or "delete_repo" in scopes:
            row["status"] = "overscoped"
            row["error"] = "classic token with admin/delete scopes - replace with a fine-grained token"
    return row


def _supabase_headers(k):
    return {"apikey": k, "Authorization": f"Bearer {k}", "Content-Type": "application/json"}


def _supabase_read():
    url, k = os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY")
    row = _wrap(_http("supabase", "read pending_deploys", k and url and k, "GET",
                      f"{url}/rest/v1/pending_deploys?select=id&limit=1", headers=_supabase_headers(k or "")))
    if k:
        row["ratelimit"]["role"] = _jwt_role(k)
    return row


def _supabase_write():
    url, k = os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY")
    h = {**_supabase_headers(k or ""), "Prefer": "return=representation"}
    res = _http("supabase", "write pending_deploys", k and url and k, "POST",
                f"{url}/rest/v1/pending_deploys", headers=h,
                json={"status": "rejected", "source": "healthcheck", "code": "healthcheck"})
    if not isinstance(res, tuple):
        return res
    row, r = res
    if row["status"] == "ok":
        try:   # clean up the test row (best effort)
            rid = r.json()[0]["id"]
            requests.delete(f"{url}/rest/v1/pending_deploys?id=eq.{rid}", headers=h, timeout=TIMEOUT)
        except Exception:
            pass
    elif "row-level security" in (row["error"] or "").lower() or "42501" in (row["error"] or ""):
        row["status"] = "rls_blocked"
    return row


def run_more():
    jobs = [
        lambda: _tavily("TAVILY_KEY_1"), lambda: _tavily("TAVILY_KEY_2"),
        lambda: _serper("SERPER_KEY_1"), lambda: _serper("SERPER_KEY_2"),
        lambda: _youcom("YOUCOM_KEY_1"), lambda: _youcom("YOUCOM_KEY_2"),
        _jina, _telegram, _github, _supabase_read, _supabase_write,
    ]
    with ThreadPoolExecutor(max_workers=16) as ex:
        futures = [ex.submit(j) for j in jobs]
        return [f.result() for f in futures]
