"""
intent.py - Intent Classifier
Checks what the user wants before routing.
Returns: image | automation | search | ask
"""

import os, json, hashlib
import urllib.request

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

INTENTS = ["image", "automation", "search", "scraping", "ask"]

SYSTEM_PROMPT = """You are an intent classifier for a personal AI assistant.
Given a user message, return ONLY a JSON object like:
{"intent": "image", "confidence": 0.95}

Intent options:
- "image": user wants an image generated (poster, drawing, photo, render, visualization, art)
- "automation": user wants to scrape, automate, extract data, fill forms, run scripts, schedule tasks
- "search": user wants current news, prices, scores, live data, recent events
- "scraping": user wants to extract content, data, or text from a specific website URL
- "ask": general question, analysis, coding help, explanation, conversation

Return ONLY the JSON. No explanation. No markdown."""

def _hash(prompt: str) -> str:
    return hashlib.md5(prompt.strip().lower().encode()).hexdigest()

def _check_cache(prompt_hash: str) -> str | None:
    url = f"{SUPABASE_URL}/rest/v1/intent_cache?prompt_hash=eq.{prompt_hash}&select=intent"
    req = urllib.request.Request(url, headers={
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}"
    })
    try:
        res = urllib.request.urlopen(req, timeout=5)
        rows = json.loads(res.read())
        if rows:
            return rows[0]["intent"]
    except:
        pass
    return None

def _save_cache(prompt_hash: str, intent: str):
    url = f"{SUPABASE_URL}/rest/v1/intent_cache"
    payload = json.dumps({"prompt_hash": prompt_hash, "intent": intent}).encode()
    req = urllib.request.Request(url, data=payload, headers={
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }, method="POST")
    try:
        urllib.request.urlopen(req, timeout=5)
    except:
        pass

def _llm_classify(prompt: str) -> str:
    """Use Groq (fast, free) to classify intent."""
    groq_key = os.getenv("GROQ_API_KEY", "")
    if not groq_key:
        return _rule_classify(prompt)

    payload = json.dumps({
        "model": "llama-3.1-8b-instant",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 50,
        "temperature": 0.1
    }).encode()

    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {groq_key}",
            "Content-Type": "application/json"
        }
    )
    try:
        res = urllib.request.urlopen(req, timeout=8)
        data = json.loads(res.read())
        text = data["choices"][0]["message"]["content"].strip()
        parsed = json.loads(text)
        intent = parsed.get("intent", "ask")
        return intent if intent in INTENTS else "ask"
    except Exception as e:
        print(f"[Intent] LLM failed: {e} — falling back to rules")
        return _rule_classify(prompt)

def _rule_classify(prompt: str) -> str:
    """Fast rule-based fallback."""
    p = prompt.lower()

    image_words = ["image", "poster", "draw", "paint", "sketch", "render", "photo", "picture",
                   "illustration", "artwork", "visualize", "generate a", "create a visual",
                   "design a", "make a poster", "8k", "4k", "cinematic", "ultra realistic"]
    if any(w in p for w in image_words):
        return "image"

    auto_words = ["scrape", "automate", "extract", "crawl", "fill form", "playwright",
                  "download data", "fetch data", "run script", "schedule", "monitor",
                  "check every", "alert me"]
    if any(w in p for w in auto_words):
        return "automation"

    search_words = ["latest", "current", "today", "news", "price of", "score", "live",
                    "right now", "recent", "trending", "what happened"]
    if any(w in p for w in search_words):
        return "search"

    scraping_words = ["scrape", "extract from", "get data from", "fetch content",
                      "pull data from", "get content from", "read from site",
                      "get text from", "fetch from url", "extract content"]
    if any(w in p for w in scraping_words):
        return "scraping"

    return "ask"

def classify(prompt: str) -> str:
    """Main entry point. Returns intent string."""
    h = _hash(prompt)

    # Check cache first
    cached = _check_cache(h)
    if cached:
        print(f"[Intent] cached → {cached}")
        return cached

    # LLM classify
    intent = _llm_classify(prompt)
    print(f"[Intent] classified → {intent}")

    # Cache it
    _save_cache(h, intent)
    return intent
