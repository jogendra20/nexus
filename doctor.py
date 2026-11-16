"""Nexus provider doctor.

Run locally or in the Render/production shell:
    python doctor.py                 # configuration inventory only
    python doctor.py --live          # calls configured providers
    python doctor.py --live --json   # machine-readable output

The doctor never prints key values or model responses. Live checks make one
small request per configured provider and should be run sparingly because
provider quotas may be consumed.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import time
from typing import Callable


CHECKS: list[tuple[str, str, Callable[[], object]]] = []


def _category(exc: Exception) -> str:
    text = str(exc).lower()
    match = re.search(r"\b(401|402|403|404|408|409|429|5\d\d)\b", text)
    if match:
        code = int(match.group(1))
        if code in (401, 403):
            return "auth_or_permission_failed"
        if code == 404:
            return "model_or_endpoint_not_found"
        if code == 429:
            return "rate_limited_or_quota_exhausted"
        if code == 402:
            return "billing_or_credits_required"
        if code >= 500:
            return "provider_server_error"
        return f"http_{code}"
    if any(word in text for word in ("timeout", "timed out", "connection", "dns", "urlerror")):
        return "network_error"
    return "provider_error"


def _safe_call(name: str, env_name: str, fn: Callable[[], object], live: bool) -> dict:
    present = bool(os.getenv(env_name, "").strip()) if env_name else True
    result = {"provider": name, "credential": env_name or None, "configured": present}
    if not present:
        result["status"] = "config_missing"
        return result
    if not live:
        result["status"] = "configured_not_tested"
        return result
    started = time.monotonic()
    try:
        value = fn()
        if isinstance(value, dict) and value.get("success") is False:
            result["status"] = "provider_error"
        elif value is None or value == "":
            result["status"] = "empty_response"
        else:
            result["status"] = "ok"
    except Exception as exc:
        result["status"] = _category(exc)
        result["exception_type"] = type(exc).__name__
    result["duration_ms"] = round((time.monotonic() - started) * 1000)
    return result


def build_checks() -> list[tuple[str, str, Callable[[], object]]]:
    from providers.cerebras import CerebrasProvider
    from providers.duck import DuckProvider
    from providers.gemini import GeminiProvider
    from providers.groq_provider import GroqProvider
    from providers.huggingface import HuggingFaceProvider
    from providers.jina import JinaProvider
    from providers.mistral import MistralProvider
    from providers.nvidia import NvidiaProvider
    from providers.openrouter import OpenRouterProvider
    from providers.search import SearchProvider

    prompt = "Reply with only the word OK."
    return [
        ("groq", "GROQ_KEY", lambda: GroqProvider().ask(prompt, "default")),
        ("cerebras", "CEREBRAS_KEY", lambda: CerebrasProvider().ask(prompt, "default")),
        ("gemini", "GEMINI_KEY", lambda: GeminiProvider().ask(prompt)),
        ("nvidia", "NVIDIA_KEY", lambda: NvidiaProvider().ask(prompt, "default")),
        ("mistral", "MISTRAL_KEY", lambda: MistralProvider().ask(prompt, "default")),
        ("openrouter", "OPENROUTER_KEY", lambda: OpenRouterProvider().ask(prompt, "default")),
        ("huggingface", "HF_TOKEN", lambda: HuggingFaceProvider().ask(prompt)),
        ("duck", "PUBLIC_SESSION", lambda: DuckProvider().ask(prompt, "default")),
        ("search", "SEARCH_PROVIDER_KEYS", lambda: SearchProvider().search("Nexus health check", max_results=1)),
        ("jina", "JINA_API_KEY", lambda: JinaProvider().fetch("https://example.com")),
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="make one live request per configured provider")
    parser.add_argument("--json", action="store_true", help="print JSON instead of a human-readable report")
    args = parser.parse_args()

    results = []
    for name, env_name, fn in build_checks():
        if env_name == "SEARCH_PROVIDER_KEYS":
            env_name = "TAVILY_KEY_1/SERPER_KEY_1/YOUCOM_KEY_1"
            configured = any(os.getenv(k, "").strip() for k in ("TAVILY_KEY_1", "TAVILY_KEY_2", "SERPER_KEY_1", "SERPER_KEY_2", "YOUCOM_KEY_1", "YOUCOM_KEY_2"))
            if not configured:
                results.append({"provider": name, "credential": env_name, "configured": False, "status": "config_missing"})
                continue
            if not args.live:
                result = {"provider": name, "credential": env_name, "configured": True, "status": "configured_not_tested"}
            else:
                started = time.monotonic()
                try:
                    value = fn()
                    result = {"provider": name, "credential": env_name, "configured": True, "status": "ok" if value and value.get("results") else "empty_response"}
                except Exception as exc:
                    result = {"provider": name, "credential": env_name, "configured": True, "status": _category(exc), "exception_type": type(exc).__name__}
                result["duration_ms"] = round((time.monotonic() - started) * 1000)
            result["credential"] = env_name
        elif env_name == "PUBLIC_SESSION":
            result = _safe_call(name, "", fn, args.live)
        else:
            result = _safe_call(name, env_name, fn, args.live)
        results.append(result)

    configured = sum(1 for r in results if r["configured"])
    healthy = sum(1 for r in results if r["status"] == "ok")
    summary = {
        "live": args.live,
        "providers_checked": len(results),
        "configured": configured,
        "healthy": healthy,
        "results": results,
    }
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(f"Nexus provider doctor | live={args.live} | configured={configured}/{len(results)} | healthy={healthy}")
        for result in results:
            print(f"- {result['provider']:15} {result['status']}")
    return 0 if all(r["status"] in {"ok", "configured_not_tested", "config_missing"} for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
