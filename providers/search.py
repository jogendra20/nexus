"""
search.py - NEXUS Search Provider
Absorbs DRONA: Tavily + Serper + You.com with fallback chain.
Sync version (no asyncio) for Flask compatibility.
"""

import os
import requests

# Keys
TAVILY_KEY_1  = os.getenv("TAVILY_KEY_1")
TAVILY_KEY_2  = os.getenv("TAVILY_KEY_2")
SERPER_KEY_1  = os.getenv("SERPER_KEY_1")
SERPER_KEY_2  = os.getenv("SERPER_KEY_2")
YOUCOM_KEY_1  = os.getenv("YOUCOM_KEY_1")
YOUCOM_KEY_2  = os.getenv("YOUCOM_KEY_2")

TIMEOUT = 10

FRESHNESS_TAVILY = {"day": 1, "week": 7, "month": 30, "any": None}
FRESHNESS_SERPER = {"day": "qdr:d", "week": "qdr:w", "month": "qdr:m", "any": None}

def _domain(url: str) -> str:
    try:
        return url.split("/")[2].replace("www.", "")
    except:
        return ""

def _deduplicate(results: list) -> list:
    seen = set()
    out = []
    for r in results:
        url = r.get("url", "")
        if url and url not in seen:
            seen.add(url)
            out.append(r)
    return out

# ── Tavily ────────────────────────────────────────────────────────
def _tavily(key: str, query: str, max_results: int, freshness: str) -> list:
    payload = {
        "api_key": key,
        "query": query,
        "max_results": max_results,
        "include_answer": False,
        "topic": "news",
        "search_depth": "basic",
    }
    days = FRESHNESS_TAVILY.get(freshness)
    if days:
        payload["days"] = days

    r = requests.post("https://api.tavily.com/search", json=payload, timeout=TIMEOUT)
    r.raise_for_status()
    results = []
    for item in r.json().get("results", []):
        results.append({
            "title":          item.get("title", ""),
            "url":            item.get("url", ""),
            "snippet":        item.get("content", ""),
            "published_date": item.get("published_date", ""),
            "source":         _domain(item.get("url", "")),
        })
    return results

# ── Serper ────────────────────────────────────────────────────────
def _serper(key: str, query: str, max_results: int, freshness: str) -> list:
    payload = {"q": query, "num": max_results}
    tbs = FRESHNESS_SERPER.get(freshness)
    if tbs:
        payload["tbs"] = tbs

    r = requests.post(
        "https://google.serper.dev/news",
        json=payload,
        headers={"X-API-KEY": key, "Content-Type": "application/json"},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    results = []
    items = r.json().get("news", r.json().get("organic", []))
    for item in items[:max_results]:
        results.append({
            "title":          item.get("title", ""),
            "url":            item.get("link", ""),
            "snippet":        item.get("snippet", ""),
            "published_date": item.get("date", ""),
            "source":         item.get("source", _domain(item.get("link", ""))),
        })
    return results

# ── You.com ───────────────────────────────────────────────────────
def _youcom(key: str, query: str, max_results: int) -> list:
    r = requests.get(
        "https://api.ydc-index.io/search",
        params={"query": query, "num_web_results": max_results},
        headers={"X-API-Key": key},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    results = []
    for item in r.json().get("hits", [])[:max_results]:
        snippet = " ".join(item.get("snippets", []))[:300]
        results.append({
            "title":          item.get("title", ""),
            "url":            item.get("url", ""),
            "snippet":        snippet,
            "published_date": "",
            "source":         _domain(item.get("url", "")),
        })
    return results

# ── Main search function ──────────────────────────────────────────
class SearchProvider:
    CHAIN = [
        ("tavily",  TAVILY_KEY_1),
        ("tavily",  TAVILY_KEY_2),
        ("serper",  SERPER_KEY_1),
        ("serper",  SERPER_KEY_2),
        ("youcom",  YOUCOM_KEY_1),
        ("youcom",  YOUCOM_KEY_2),
    ]

    def search(self, query: str, max_results: int = 5, freshness: str = "day") -> dict:
        for provider, key in self.CHAIN:
            if not key:
                continue
            try:
                if provider == "tavily":
                    results = _tavily(key, query, max_results, freshness)
                elif provider == "serper":
                    results = _serper(key, query, max_results, freshness)
                elif provider == "youcom":
                    results = _youcom(key, query, max_results)

                if results:
                    print(f"[Search] {provider} returned {len(results)} results")
                    return {
                        "results":  _deduplicate(results),
                        "provider": provider,
                    }
            except Exception as e:
                print(f"[Search] {provider} failed: {e} — trying next")
                continue

        return {"results": [], "provider": None}

    def ask(self, prompt: str) -> str:
        """Compatible with NEXUS provider interface."""
        data = self.search(prompt)
        results = data.get("results", [])
        if not results:
            return "No search results found."
        lines = []
        for r in results[:5]:
            lines.append(f"- {r['title']} ({r['source']}): {r['snippet']}")
        return "\n".join(lines)
