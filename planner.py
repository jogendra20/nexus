import os
import json
import urllib.request
from datetime import datetime, timezone

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
GROQ_KEY = os.getenv("GROQ_KEY", "")
OPENROUTER_KEY = os.getenv("OPENROUTER_KEY", "")

PLAN_SYSTEM_PROMPT = """You are a task planner for a personal AI assistant.
Given a goal, break it into 2-5 concrete steps.
Each step must have:
- name: short label
- type: one of [search, scraping, automation, reasoning, notify]
- prompt: exact instruction for that step
- depends_on: index of step this depends on (-1 if none)

Return ONLY a JSON array. No explanation. No markdown.

Example:
[
  {"name": "fetch data", "type": "scraping", "prompt": "scrape nse.com announcements", "depends_on": -1},
  {"name": "summarize", "type": "reasoning", "prompt": "summarize these announcements: {step_0_output}", "depends_on": 0},
  {"name": "notify", "type": "notify", "prompt": "send summary to telegram", "depends_on": 1}
]"""


def _headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }


def plan_goal(goal: str) -> list:
    """Use Groq to break a goal into steps."""
    if not GROQ_KEY:
        return []

    payload = json.dumps({
        "model": "llama-3.1-8b-instant",
        "messages": [
            {"role": "system", "content": PLAN_SYSTEM_PROMPT},
            {"role": "user", "content": goal}
        ],
        "max_tokens": 500,
        "temperature": 0.2
    }).encode()

    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {GROQ_KEY}",
            "Content-Type": "application/json"
        }
    )
    try:
        res = urllib.request.urlopen(req, timeout=10)
        data = json.loads(res.read())
        text = data["choices"][0]["message"]["content"].strip()
        text = text.replace("```json", "").replace("```", "").strip()
        steps = json.loads(text)
        return steps if isinstance(steps, list) else []
    except Exception as e:
        print(f"[Planner] Groq failed: {e}")
        return []


def save_task(goal: str, steps: list, schedule: str) -> str:
    """Save a scheduled task to Supabase. Returns task id."""
    payload = json.dumps({
        "goal": goal,
        "steps": steps,
        "schedule": schedule,
        "status": "active",
        "created_at": datetime.now(timezone.utc).isoformat()
    }).encode()

    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/scheduled_tasks",
        data=payload,
        headers={**_headers(), "Prefer": "return=representation"},
        method="POST"
    )
    try:
        res = urllib.request.urlopen(req, timeout=8)
        rows = json.loads(res.read())
        return rows[0]["id"] if rows else ""
    except Exception as e:
        print(f"[Planner] save_task failed: {e}")
        return ""


def get_active_tasks() -> list:
    """Fetch all active scheduled tasks."""
    url = f"{SUPABASE_URL}/rest/v1/scheduled_tasks?status=eq.active&select=*"
    req = urllib.request.Request(url, headers={
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}"
    })
    try:
        res = urllib.request.urlopen(req, timeout=8)
        return json.loads(res.read())
    except Exception as e:
        print(f"[Planner] get_active_tasks failed: {e}")
        return []


def save_run(task_id: str, step_index: int, step_name: str,
             status: str, output: str = "", error: str = "") -> str:
    """Log one step execution to task_runs. Returns run id."""
    payload = json.dumps({
        "task_id": task_id,
        "step_index": step_index,
        "step_name": step_name,
        "status": status,
        "output": output[:1000],
        "error": error[:500],
        "created_at": datetime.now(timezone.utc).isoformat()
    }).encode()

    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/task_runs",
        data=payload,
        headers={**_headers(), "Prefer": "return=representation"},
        method="POST"
    )
    try:
        res = urllib.request.urlopen(req, timeout=8)
        rows = json.loads(res.read())
        return rows[0]["id"] if rows else ""
    except Exception as e:
        print(f"[Planner] save_run failed: {e}")
        return ""


def get_runs(task_id: str) -> list:
    """Get all runs for a task, ordered by step."""
    url = f"{SUPABASE_URL}/rest/v1/task_runs?task_id=eq.{task_id}&order=step_index.asc&select=*"
    req = urllib.request.Request(url, headers={
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}"
    })
    try:
        res = urllib.request.urlopen(req, timeout=8)
        return json.loads(res.read())
    except Exception as e:
        print(f"[Planner] get_runs failed: {e}")
        return []
