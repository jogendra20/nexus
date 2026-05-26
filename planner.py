import os
import json
import urllib.request
from datetime import datetime, timezone

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

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


def plan_goal(goal: str, router) -> list:
    """Use Nexus router to break a goal into steps."""
    prompt = PLAN_SYSTEM_PROMPT + f"\n\nGoal: {goal}"
    try:
        result = router.ask(prompt, task="reasoning", difficulty="medium")
        text = result.get("response", "").strip()
        text = text.replace("```json", "").replace("```", "").strip()
        start = text.find("[")
        end = text.rfind("]") + 1
        if start == -1 or end == 0:
            print(f"[Planner] No JSON array found in: {text[:200]}")
            return []
        steps = json.loads(text[start:end])
        return steps if isinstance(steps, list) else []
    except Exception as e:
        print(f"[Planner] plan_goal failed: {e}")
        return []


def save_task(goal: str, steps: list, schedule: str) -> str:
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
