"""
scorer.py - Self-Learning Quality Scorer
Scores persist in Supabase — survives Render redeploys.
"""

import os
import json
from datetime import datetime, timezone

# Load .env locally
try:
    with open(os.path.join(os.path.dirname(__file__), ".env")) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())
except FileNotFoundError:
    pass

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

DEFAULT_SCORES = {
    "github_models": {"reasoning": 10, "premium": 10, "coding": 9,  "trading": 7,  "search": 5,  "default": 8},
    "nvidia":        {"reasoning": 9,  "premium": 9,  "coding": 8,  "trading": 7,  "search": 5,  "default": 7},
    "cerebras":      {"reasoning": 6,  "premium": 5,  "coding": 6,  "trading": 9,  "search": 4,  "default": 8},
    "gemini":        {"reasoning": 8,  "premium": 8,  "coding": 7,  "trading": 8,  "search": 8,  "default": 8},
    "groq":          {"reasoning": 6,  "premium": 5,  "coding": 6,  "trading": 8,  "search": 5,  "default": 7},
    "mistral":       {"reasoning": 6,  "premium": 6,  "coding": 10, "trading": 5,  "search": 4,  "default": 6},
    "openrouter":    {"reasoning": 7,  "premium": 7,  "coding": 7,  "trading": 6,  "search": 5,  "default": 6},
    "huggingface":   {"reasoning": 7,  "premium": 6,  "coding": 7,  "trading": 5,  "search": 4,  "default": 6},
    "drona":         {"reasoning": 2,  "premium": 2,  "coding": 2,  "trading": 6,  "search": 10, "default": 3},
}

LEARNING_RATE = 0.1
MIN_SCORE     = 1.0
MAX_SCORE     = 10.0


def _headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal"
    }


def _get(provider: str) -> dict | None:
    """Fetch one provider row from Supabase."""
    import urllib.request
    url = f"{SUPABASE_URL}/rest/v1/provider_scores?provider=eq.{provider}&select=scores"
    req = urllib.request.Request(url, headers={
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}"
    })
    try:
        res = urllib.request.urlopen(req, timeout=5)
        rows = json.loads(res.read())
        if rows:
            return rows[0]["scores"]
    except Exception as e:
        print(f"[Scorer] Supabase GET failed: {e}")
    return None


def _upsert(provider: str, scores: dict):
    """Write provider scores to Supabase."""
    import urllib.request
    url = f"{SUPABASE_URL}/rest/v1/provider_scores"
    payload = json.dumps({
        "provider": provider,
        "scores": scores,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }).encode()
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }
    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    try:
        urllib.request.urlopen(req, timeout=5)
    except Exception as e:
        print(f"[Scorer] Supabase UPSERT failed: {e}")


def load_scores() -> dict:
    """Load all provider scores from Supabase. Falls back to defaults."""
    import urllib.request
    url = f"{SUPABASE_URL}/rest/v1/provider_scores?select=provider,scores"
    req = urllib.request.Request(url, headers={
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}"
    })
    try:
        res = urllib.request.urlopen(req, timeout=5)
        rows = json.loads(res.read())
        if rows:
            return {r["provider"]: r["scores"] for r in rows}
    except Exception as e:
        print(f"[Scorer] load_scores failed: {e}")

    # Nothing in DB yet — seed defaults
    for provider, scores in DEFAULT_SCORES.items():
        _upsert(provider, scores)
    return DEFAULT_SCORES


def update_score(provider: str, task: str, success: bool,
                 response_time_ms: int = 0, response_length: int = 0):
    # Get current scores for this provider
    scores = _get(provider)
    if scores is None:
        scores = DEFAULT_SCORES.get(provider, {}).copy()

    if task not in scores:
        scores[task] = 5.0

    current = scores[task]

    if success:
        outcome = 1.0
        if response_time_ms > 0:
            speed_bonus = max(0, 1.0 - (response_time_ms / 10000))
            outcome += speed_bonus * 0.3
        if response_length > 0:
            length_bonus = min(response_length / 500, 1.0) * 0.2
            outcome += length_bonus
    else:
        outcome = -1.0

    new_score = current + LEARNING_RATE * (outcome * MAX_SCORE - current)
    new_score = max(MIN_SCORE, min(MAX_SCORE, new_score))
    scores[task] = round(new_score, 3)

    _upsert(provider, scores)
    print(f"[Scorer] {provider}/{task}: {current:.2f} → {new_score:.2f}")
    return new_score


def get_score(provider: str, task: str) -> float:
    scores = _get(provider)
    if scores:
        return scores.get(task, 5.0)
    return DEFAULT_SCORES.get(provider, {}).get(task, 5.0)


def print_scores():
    scores = load_scores()
    print("\n[Scorer] Current quality scores:")
    for provider, tasks in scores.items():
        avg = sum(tasks.values()) / len(tasks)
        print(f"  {provider:15} avg={avg:.2f} | {tasks}")


if __name__ == "__main__":
    print_scores()
