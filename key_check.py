"""key_check.py - test every LLM provider key from inside the deployed Nexus.

For each provider/model it sends one tiny chat request that includes a dummy tool,
so we learn three things at once: is the key valid, is the model reachable, and
does the model support tool calling (which coding agents like OpenCode need).
Key values are never returned; any error text is redacted.
"""
import os
import time
from concurrent.futures import ThreadPoolExecutor

import requests

TIMEOUT = 20

TOOL = {
    "type": "function",
    "function": {
        "name": "get_time",
        "description": "Get the current time in a timezone",
        "parameters": {
            "type": "object",
            "properties": {"timezone": {"type": "string"}},
            "required": ["timezone"],
        },
    },
}


def _uniq(values, limit):
    out = []
    for v in values:
        if v not in out:
            out.append(v)
    return out[:limit]


def _targets():
    """(provider, url, key, model, extra_headers) for every model Nexus actually uses."""
    from providers.groq_provider import GroqProvider
    from providers.cerebras import CerebrasProvider
    from providers.mistral import MistralProvider
    from providers.nvidia import NvidiaProvider
    from providers.openrouter import OpenRouterProvider
    from providers.gemini import GeminiProvider
    from providers.huggingface import HuggingFaceProvider

    t = []
    for name, cls, envs, limit in [
        ("groq", GroqProvider, ("GROQ_KEY", "GROQ_API_KEY"), 2),
        ("cerebras", CerebrasProvider, ("CEREBRAS_KEY",), 2),
        ("mistral", MistralProvider, ("MISTRAL_KEY",), 2),
        ("nvidia", NvidiaProvider, ("NVIDIA_KEY",), 3),
        ("openrouter", OpenRouterProvider, ("OPENROUTER_KEY", "OPENROUTER_API_KEY"), 1),
    ]:
        key = next((os.getenv(e) for e in envs if os.getenv(e)), None)
        extra = {"HTTP-Referer": "https://github.com/nexus"} if name == "openrouter" else {}
        for model in _uniq(cls.MODELS.values(), limit):
            t.append((name, cls.URL, key, model, extra))

    gkey = os.getenv("GEMINI_KEY") or os.getenv("GEMINI_API_KEY")
    for model in _uniq(GeminiProvider.MODELS, 2):
        t.append(("gemini", "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
                  gkey, model, {}))

    hkey = os.getenv("HF_TOKEN")
    for model in _uniq(HuggingFaceProvider.TEXT_MODELS, 2):
        t.append(("huggingface", "https://router.huggingface.co/v1/chat/completions", hkey, model, {}))
    return t


def _redact(text, key):
    text = (text or "")[:200]
    return text.replace(key, "***") if key else text


def check_one(target):
    provider, url, key, model, extra = target
    row = {"provider": provider, "model": model, "status": "", "tools": None,
           "latency_ms": None, "ratelimit": {}, "error": ""}
    if not key:
        row["status"] = "no_key"
        return row
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json", **extra}
    body = {
        "model": model,
        "messages": [{"role": "user", "content": "What time is it in UTC? Use the get_time tool."}],
        "tools": [TOOL],
        "tool_choice": "auto",
        "max_tokens": 256,
    }
    start = time.time()
    try:
        r = requests.post(url, headers=headers, json=body, timeout=TIMEOUT)
    except Exception as e:
        row["status"] = "error"
        row["error"] = _redact(f"{type(e).__name__}: {e}", key)
        return row
    row["latency_ms"] = int((time.time() - start) * 1000)
    row["ratelimit"] = {k.lower(): v for k, v in r.headers.items()
                        if k.lower().startswith("x-ratelimit") or k.lower() == "retry-after"}
    code = r.status_code
    if code in (401, 403):
        row["status"] = "auth_failed"
    elif code == 429:
        row["status"] = "rate_limited"
    elif code == 404:
        row["status"] = "model_not_found"
    elif code == 400 and "tool" in r.text.lower():
        row["status"] = "no_tool_support"
    elif 200 <= code < 300:
        try:
            msg = r.json()["choices"][0]["message"]
            row["tools"] = bool(msg.get("tool_calls"))
            row["status"] = "ok_tools" if row["tools"] else "ok_no_tool_call"
        except Exception:
            row["status"] = "bad_response"
    else:
        row["status"] = f"http_{code}"
    if not row["status"].startswith("ok"):
        row["error"] = _redact(r.text, key)
    return row


def run_checks():
    targets = _targets()
    with ThreadPoolExecutor(max_workers=16) as ex:
        results = list(ex.map(check_one, targets))
    return results


def as_text(results):
    lines = [f"{'provider':<12}{'model':<40}{'status':<17}{'ms':>6}  limits"]
    for r in results:
        rl = ",".join(f"{k.replace('x-ratelimit-', '')}={v}" for k, v in list(r["ratelimit"].items())[:3])
        lines.append(f"{r['provider']:<12}{r['model'][:38]:<40}{r['status']:<17}{(r['latency_ms'] or 0):>6}  {rl}")
        if r["error"]:
            lines.append(f"{'':<12}↳ {r['error'][:110]}")
    return "\n".join(lines) + "\n"
