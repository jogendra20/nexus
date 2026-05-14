import os
import requests

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

def log_request(prompt: str, task: str, provider: str, model: str = None,
                success: bool = True, error: str = None,
                scores: dict = None, response_time_ms: int = 0):
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("[Logger] Missing Supabase keys")
        return

    payload = {
        "prompt":           prompt[:500],
        "task":             task,
        "provider":         provider,
        "model":            model,
        "success":          success,
        "error":            error,
        "quality":          scores.get("quality")      if scores else None,
        "availability":     scores.get("availability") if scores else None,
        "final_score":      scores.get("final")        if scores else None,
        "response_time_ms": response_time_ms,
    }

    try:
        r = requests.post(
            f"{SUPABASE_URL}/rest/v1/nexus_logs",
            headers={
                "apikey":        SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type":  "application/json",
            },
            json=payload,
            timeout=5,
        )
        print(f"[Logger] Status: {r.status_code} | {r.text[:100]}")
    except Exception as e:
        print(f"[Logger] Failed: {e}")
