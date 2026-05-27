from flask import Flask, request, jsonify
from datetime import datetime
from router import Router
from auth import auth_required
import os
import requests
import base64

from flask_cors import CORS
app = Flask(__name__)
CORS(app, origins=["https://*.vercel.app", "http://localhost:3000"])
router = Router()

import threading, time as _time
_skills_cache = {"content": "", "loaded_at": 0}
_SKILLS_TTL = 21600

def _load_skills():
    import requests as _req
    try:
        res = _req.get(
            "https://raw.githubusercontent.com/jogendra20/Automate/main/skills/playwright.md",
            timeout=10
        )
        if res.status_code == 200:
            _skills_cache["content"] = res.text
            _skills_cache["loaded_at"] = _time.time()
            print(f"[Skills] Loaded {len(res.text)} chars")
    except Exception as e:
        print(f"[Skills] Load failed: {e}")

def get_skills() -> str:
    if _time.time() - _skills_cache["loaded_at"] > _SKILLS_TTL:
        threading.Thread(target=_load_skills, daemon=True).start()
    return _skills_cache["content"]

_load_skills()

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

@app.route("/status", methods=["GET"])
def status():
    return jsonify(router.status())

@app.route("/ask", methods=["POST"])
def ask():
    if not auth_required():
        return jsonify({"error": "Unauthorized"}), 401
    data = request.json
    prompt = data.get("prompt", "")
    skip_clarify = data.get("skip_clarify", False)

    if not skip_clarify:
        from clarifier import analyze_prompt
        analysis = analyze_prompt(prompt, router)
        if analysis["action"] == "clarify":
            return jsonify({
                "clarify": True,
                "question": analysis["result"],
                "original_prompt": prompt
            })
        elif analysis["action"] == "enhance":
            prompt = analysis["result"]

    result = router.ask(prompt, data.get("task"), data.get("difficulty", "easy"))
    result["original_prompt"] = data.get("prompt", "")
    result["enhanced"] = prompt != data.get("prompt", "")
    return jsonify(result)

@app.route("/search", methods=["POST"])
def search():
    if not auth_required():
        return jsonify({"error": "Unauthorized"}), 401
    data = request.json
    query       = data.get("query", "")
    max_results = data.get("max_results", 5)
    freshness   = data.get("freshness", "day")
    result = router.providers["search"].search(query, max_results, freshness)
    return jsonify(result)

@app.route("/image", methods=["POST"])
def image():
    if not auth_required():
        return jsonify({"error": "Unauthorized"}), 401
    data = request.json
    prompt = data.get("prompt")
    if not prompt:
        return jsonify({"error": "prompt required"}), 400
    try:
        result = router.generate_image(prompt)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/telegram", methods=["POST"])
def telegram_webhook():
    from telegram_bot import handle_update
    update = request.json
    handle_update(update)
    return "ok"


@app.route("/deploy", methods=["POST"])
def deploy():
    import threading
    if not auth_required():
        return jsonify({"error": "Unauthorized"}), 401
    data = request.json
    prompt   = data.get("prompt", "")
    filename   = data.get("filename", None)
    task       = data.get("task", "automation")
    difficulty = data.get("difficulty", "easy")

    if not prompt:
        return jsonify({"error": "prompt required"}), 400

    # Step 1: Generate code via Nexus router
    result = router.ask(prompt, task=task, difficulty=difficulty)
    code   = result.get("response", "")
    provider = result.get("provider", "unknown")

    if not code or code.strip() == "" or "All providers exhausted" in code:
        return jsonify({"error": "Code generation failed", "provider": provider}), 503

    # Strip markdown fences and trailing prose
    import re
    code = re.sub(r"^```(?:python)?\n?|```$", "", code, flags=re.MULTILINE).strip()
    # Remove any lines after the last Python line (trailing explanations)
    lines = code.splitlines()
    last_code_line = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and any(c in stripped for c in ["(", ")", "=", ":", "import", "from", "print", "for", "if", "with", "def", "class", "return", "try", "except"]):
            last_code_line = i
    code = "\n".join(lines[:last_code_line + 1]).strip()

    # Step 2: Push to GitHub
    from github_pusher import push_script, trigger_workflow
    push_result = push_script(code, filename)

    if not push_result["success"]:
        return jsonify({"error": "Push failed", "detail": push_result}), 500

    # Step 3: Trigger workflow
    trigger_result = trigger_workflow(push_result["filename"], prompt[:100], difficulty, provider)

    # Step 4: Notify Telegram
    import os, requests as req
    token   = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if token and chat_id:
        status = "✅ triggered" if trigger_result["success"] else "⚠️ push ok, trigger failed"
        req.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": f"🤖 *Nexus Automation*\n\n`{push_result['filename']}`\nProvider: {provider}\nStatus: {status}\n\n[View file]({push_result['url']})",
                "parse_mode": "Markdown"
            }
        )

    run_id = trigger_result.get("run_id") or push_result["filename"].replace("scripts/","").replace(".py","")
    return jsonify({
        "code": code,
        "provider": provider,
        "file": push_result["filename"],
        "triggered": trigger_result["success"],
        "run_id": run_id,
    })

@app.route("/delete-script", methods=["POST"])
def delete_script():
    if not auth_required():
        return jsonify({"error": "Unauthorized"}), 401
    data = request.json
    filepath = data.get("filepath")
    if not filepath:
        return jsonify({"error": "filepath required"}), 400
    from github_pusher import delete_file
    result = delete_file(filepath)
    return jsonify(result)


@app.route("/output", methods=["POST"])
def output():
    if not auth_required():
        return jsonify({"error": "Unauthorized"}), 401
    data = request.json
    run_id = str(data.get("run_id", ""))
    import urllib.request as _ur, json as _json
    sb_url = os.getenv("SUPABASE_URL", "")
    sb_key = os.getenv("SUPABASE_KEY", "")
    url = f"{sb_url}/rest/v1/run_outputs?run_id=eq.{run_id}&select=*"
    req = _ur.Request(url, headers={
        "apikey": sb_key,
        "Authorization": f"Bearer {sb_key}"
    })
    try:
        res = _ur.urlopen(req, timeout=5)
        rows = _json.loads(res.read())
        if rows:
            return jsonify(rows[0])
    except Exception as e:
        print(f"[Output] Supabase error: {e}")
    return jsonify({"status": "pending", "output": None})

@app.route("/store-output", methods=["POST"])
def store_output():
    """Called by send_output.py to store run results in Supabase."""
    if not auth_required():
        return jsonify({"error": "Unauthorized"}), 401
    data = request.json
    run_id = str(data.get("run_id", ""))
    if not run_id:
        return jsonify({"error": "run_id required"}), 400
    import urllib.request as _ur, json as _json
    sb_url = os.getenv("SUPABASE_URL", "")
    sb_key = os.getenv("SUPABASE_KEY", "")
    payload = _json.dumps({
        "run_id": run_id,
        "status": data.get("status", "done"),
        "output": data.get("output", ""),
        "image_b64": data.get("image_b64"),
        "task": data.get("task", ""),
        "exit_code": data.get("exit_code", 0)
    }).encode()
    req = _ur.Request(
        f"{sb_url}/rest/v1/run_outputs",
        data=payload,
        headers={
            "apikey": sb_key,
            "Authorization": f"Bearer {sb_key}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates"
        },
        method="POST"
    )
    try:
        _ur.urlopen(req, timeout=10)
        return jsonify({"stored": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/ticker", methods=["GET"])
def ticker():
    from ticker import get_ticker
    items = get_ticker()
    return jsonify({"items": items})

@app.route("/ticker", methods=["POST"])
def classify_intent():
    if not auth_required():
        return jsonify({"error": "Unauthorized"}), 401
    data = request.json
    prompt = data.get("prompt", "")
    if not prompt:
        return jsonify({"error": "prompt required"}), 400
    from intent import classify
    intent = classify(prompt)
    return jsonify({"intent": intent})

@app.route("/result", methods=["POST"])
def result():
    if not auth_required():
        return jsonify({"error": "Unauthorized"}), 401
    data = request.json
    # data: {provider, task, success, response_time_ms, error}
    from scorer import update_score
    from logger import log_request
    update_score(
        provider=data.get("provider", "unknown"),
        task=data.get("task", "automation"),
        success=data.get("success", False),
        response_time_ms=data.get("response_time_ms", 0),
    )
    if not data.get("success") and data.get("error"):
        import os, requests as req
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        chat_id = os.getenv("TELEGRAM_CHAT_ID")
        if token and chat_id:
            req.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": f"❌ Automation failed\n`{data.get('error','')[:300]}`", "parse_mode": "Markdown"}
            )
    return jsonify({"status": "scored"})

@app.route("/enhance", methods=["POST"])
def enhance():
    if not auth_required():
        return jsonify({"error": "Unauthorized"}), 401
    data = request.json
    prompt = data.get("prompt", "").strip().lower()
    if not prompt:
        return jsonify({"error": "prompt required"}), 400

    import re

    # Extract URL if present
    url_match = re.search(r"(https?://\S+|www\.\S+|\S+\.(com|in|org|net|ac\.in|edu|gov)\S*)", prompt)
    url = url_match.group(0) if url_match else None
    if url and not url.startswith("http"):
        url = "https://" + url

    # Detect intent
    screenshot_kw = ["screenshot", "photo", "picture", "capture", "look", "see", "show"]
    scrape_kw     = ["scrape", "extract", "get data", "fetch", "list", "gainers", "losers", "price", "news"]
    fill_kw       = ["fill", "login", "form", "submit", "register"]
    monitor_kw    = ["monitor", "watch", "check every", "alert"]

    if any(k in prompt for k in screenshot_kw):
        action = f"go to {url or 'the website'}, wait 30 seconds, save a screenshot as screenshot.png"
    elif any(k in prompt for k in fill_kw):
        action = f"go to {url or 'the website'}, fill the form and submit, print confirmation"
    elif any(k in prompt for k in monitor_kw):
        action = f"go to {url or 'the website'}, monitor for changes every 60 seconds, print any updates"
    elif any(k in prompt for k in scrape_kw):
        action = f"scrape {url or 'the target page'}, extract the relevant data, print as a clean list"
    elif url:
        action = f"go to {url}, wait for full page load, save a screenshot as screenshot.png"
    else:
        # Can't enhance without enough signal — pass through as-is
        return jsonify({"enhanced": None})

    enhanced = action
    return jsonify({"enhanced": enhanced, "provider": "local"})

@app.route("/fix", methods=["POST"])
def fix():
    if not auth_required():
        return jsonify({"error": "Unauthorized"}), 401
    data = request.json
    prompt = data.get("prompt", "")
    error = data.get("error", "")
    code = data.get("code", "")

    if not prompt:
        return jsonify({"error": "prompt required"}), 400

    fix_prompt = f"""A Python automation script failed. You must write a complete fixed version.

Original task: {prompt}

Failed code:
{code[:2000]}

Error output:
{error[:1000]}

Rules:
- Analyze why the code failed from the error output
- Write a complete working replacement script
- If the error is JSONDecodeError or RemoteDisconnected on nseindia.com, switch to Tickertape API: https://api.tickertape.in/stocks/screener/filter?sortBy=change_percent&sortOrder=desc&limit=10
- Output ONLY raw Python code. Not the word "Fixed". Not an explanation. A complete runnable Python script.
- The script must print actual results"""

    result = router.ask(fix_prompt, task="automation")
    fixed_code = result.get("response", "")
    provider = result.get("provider", "unknown")

    if not fixed_code or "All providers exhausted" in fixed_code:
        return jsonify({"error": "Fix generation failed"}), 503

    import re
    fixed_code = re.sub(r"^```(?:python)?\n?|```$", "", fixed_code, flags=re.MULTILINE).strip()

    from github_pusher import push_script, trigger_workflow
    push_result = push_script(fixed_code, None)

    if not push_result["success"]:
        return jsonify({"error": "Push failed", "detail": push_result}), 500

    trigger_result = trigger_workflow(push_result["filename"], f"[RETRY] {prompt[:80]}", "medium", provider)

    import os, requests as req
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if token and chat_id:
        status = "✅ retry triggered" if trigger_result["success"] else "⚠️ fix generated, trigger failed"
        req.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": f"🔧 *Nexus Auto-Fix*\n\nProvider: {provider}\nStatus: {status}\n\n[View fixed script]({push_result['url']})",
                "parse_mode": "Markdown"
            }
        )

    return jsonify({
        "fixed": True,
        "provider": provider,
        "file": push_result["filename"],
        "triggered": trigger_result["success"]
    })

@app.route("/orchestrate", methods=["POST"])
def orchestrate():
    if not auth_required():
        return jsonify({"error": "Unauthorized"}), 401
    data = request.json
    query = data.get("prompt", "")
    if not query:
        return jsonify({"error": "prompt required"}), 400
    from orchestrator_agent import run as orch_run
    result = orch_run(query, router)
    return jsonify(result)

@app.route("/reload-skills", methods=["POST"])
def reload_skills():
    if not auth_required():
        return jsonify({"error": "Unauthorized"}), 401
    _load_skills()
    return jsonify({"status": "reloaded", "chars": len(_skills_cache["content"])})


# ── Recon system ──────────────────────────────────────────────────

import json as _json

_recon_cache = {}  # site_key -> recon data (in-memory, backed by GitHub)
_pending_approvals = {}  # site_key -> {"old": ..., "new": ..., "chat_id": ...}

GITHUB_RAW = "https://raw.githubusercontent.com/jogendra20/Automate/main/skills/sites.json"
GITHUB_API = "https://api.github.com/repos/jogendra20/Automate/contents/skills/sites.json"

def _load_sites_json():
    try:
        r = requests.get(GITHUB_RAW, timeout=8)
        if r.status_code == 200:
            return r.json()
    except:
        pass
    return {}

def _save_sites_json(data: dict):
    import base64
    token = os.getenv("GITHUB_TOKEN")
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json"
    }
    check = requests.get(GITHUB_API, headers=headers, timeout=8)
    sha = check.json().get("sha") if check.status_code == 200 else None
    content_b64 = base64.b64encode(_json.dumps(data, indent=2).encode()).decode()
    payload = {"message": "auto: update sites.json", "content": content_b64, "branch": "main"}
    if sha:
        payload["sha"] = sha
    requests.put(GITHUB_API, headers=headers, json=payload, timeout=10)

@app.route("/store-recon", methods=["POST"])
def store_recon():
    if not auth_required():
        return jsonify({"error": "Unauthorized"}), 401
    data = request.json
    site_key = data.get("site_key", "")
    if not site_key:
        return jsonify({"error": "site_key required"}), 400

    sites = _load_sites_json()
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if site_key in sites:
        # Site exists — compare selectors
        old = sites[site_key]
        old_buttons = set(old.get("buttons", []))
        new_buttons = set(data.get("buttons", []))
        changed = old_buttons != new_buttons or old.get("has_stock_links") != data.get("has_stock_links")

        if changed:
            _pending_approvals[site_key] = {"old": old, "new": data}
            if token and chat_id:
                diff_msg = (
                    f"🔄 *Selector change detected*\n\n"
                    f"Site: `{site_key}`\n\n"
                    f"Old buttons: {list(old_buttons)[:5]}\n"
                    f"New buttons: {list(new_buttons)[:5]}\n\n"
                    f"Reply:\n"
                    f"`approve {site_key}` — update skill\n"
                    f"`reject {site_key}` — keep old"
                )
                requests.post(
                    f"https://api.telegram.org/bot{token}/sendMessage",
                    json={"chat_id": chat_id, "text": diff_msg, "parse_mode": "Markdown"},
                    timeout=10
                )
            return jsonify({"status": "pending_approval", "site_key": site_key})
        else:
            # No change — just update last_checked
            sites[site_key]["last_checked"] = data.get("run_id", "")
            _save_sites_json(sites)
            return jsonify({"status": "no_change"})
    else:
        # New site — store directly, notify
        from datetime import datetime
        data["last_checked"] = datetime.now().isoformat()
        data["working"] = True
        sites[site_key] = data
        _save_sites_json(sites)
        if token and chat_id:
            requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": (
                        f"✅ *New site added to skills*\n\n"
                        f"`{site_key}`\n"
                        f"Buttons: {data.get('buttons', [])[:5]}\n"
                        f"Stock links: {data.get('has_stock_links')}\n"
                        f"Tables: {data.get('tables')}"
                    ),
                    "parse_mode": "Markdown"
                },
                timeout=10
            )
        return jsonify({"status": "stored", "site_key": site_key})

@app.route("/approve-recon", methods=["POST"])
def approve_recon():
    if not auth_required():
        return jsonify({"error": "Unauthorized"}), 401
    site_key = request.json.get("site_key", "")
    if site_key not in _pending_approvals:
        return jsonify({"error": "No pending approval for this site"}), 404
    sites = _load_sites_json()
    from datetime import datetime
    new_data = _pending_approvals.pop(site_key)["new"]
    new_data["last_checked"] = datetime.now().isoformat()
    new_data["working"] = True
    sites[site_key] = new_data
    _save_sites_json(sites)
    return jsonify({"status": "approved", "site_key": site_key})

@app.route("/reject-recon", methods=["POST"])
def reject_recon():
    if not auth_required():
        return jsonify({"error": "Unauthorized"}), 401
    site_key = request.json.get("site_key", "")
    _pending_approvals.pop(site_key, None)
    return jsonify({"status": "rejected", "site_key": site_key})

@app.route("/get-recon", methods=["POST"])
def get_recon():
    if not auth_required():
        return jsonify({"error": "Unauthorized"}), 401
    site_key = request.json.get("site_key", "")
    sites = _load_sites_json()
    if site_key in sites:
        return jsonify({"found": True, "data": sites[site_key]})
    return jsonify({"found": False})



_pending_skill_proposals = {}

import json as _json
_PROPOSALS_FILE = "/tmp/skill_proposals.json"

def _load_proposals():
    import urllib.request as _ur
    sb_url = os.getenv("SUPABASE_URL", "")
    sb_key = os.getenv("SUPABASE_KEY", "")
    try:
        req = _ur.Request(
            f"{sb_url}/rest/v1/skill_proposals?select=*",
            headers={"apikey": sb_key, "Authorization": f"Bearer {sb_key}"}
        )
        res = _ur.urlopen(req, timeout=8)
        rows = _json.loads(res.read())
        return {row["domain"]: row for row in rows}
    except Exception as e:
        print(f"[Proposals] Supabase load failed: {e}")
        try:
            with open(_PROPOSALS_FILE) as f:
                return _json.load(f)
        except:
            return {}

def _save_proposals(data):
    import urllib.request as _ur
    sb_url = os.getenv("SUPABASE_URL", "")
    sb_key = os.getenv("SUPABASE_KEY", "")
    for domain, proposal in data.items():
        try:
            payload = _json.dumps({"domain": domain, **proposal}).encode()
            req = _ur.Request(
                f"{sb_url}/rest/v1/skill_proposals",
                data=payload,
                headers={
                    "apikey": sb_key,
                    "Authorization": f"Bearer {sb_key}",
                    "Content-Type": "application/json",
                    "Prefer": "resolution=merge-duplicates"
                },
                method="POST"
            )
            _ur.urlopen(req, timeout=8)
        except Exception as e:
            print(f"[Proposals] Supabase save failed for {domain}: {e}")
    # Always write local backup too
    try:
        with open(_PROPOSALS_FILE, "w") as f:
            _json.dump(data, f)
    except:
        pass


@app.route("/store-skill-proposal", methods=["POST"])
def store_skill_proposal():
    if not auth_required():
        return jsonify({"error": "Unauthorized"}), 401
    data = request.json
    domain = data.get("domain", "")
    if not domain:
        return jsonify({"error": "domain required"}), 400
    proposals = _load_proposals()
    proposals[domain] = {
        "task": data.get("task", ""),
        "code": data.get("code", ""),
        "output_sample": data.get("output_sample", ""),
        "run_id": data.get("run_id", "")
    }
    _save_proposals(proposals)
    return jsonify({"status": "stored", "domain": domain})

@app.route("/approve-skill", methods=["POST"])
def approve_skill():
    if not auth_required():
        return jsonify({"error": "Unauthorized"}), 401
    domain = request.json.get("domain", "")
    proposals = _load_proposals()
    if domain not in proposals:
        return jsonify({"error": "No pending proposal"}), 404
    proposal = proposals.pop(domain)
    _save_proposals(proposals)
    import base64
    token = os.getenv("GITHUB_TOKEN")
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json"
    }
    api = "https://api.github.com/repos/jogendra20/Automate/contents/skills/playwright.md"
    check = requests.get(api, headers=headers, timeout=8)
    current = base64.b64decode(check.json().get("content","")).decode() if check.status_code == 200 else ""
    sha = check.json().get("sha") if check.status_code == 200 else None
    new_recipe = (
        f"\n\n## VERIFIED RECIPE: {domain} (copy exactly, do not modify)\n\n"
        f"# Task: {proposal['task']}\n"
        f"{proposal['code']}"
    )
    updated = current + new_recipe
    payload = {
        "message": f"feat: add verified recipe for {domain}",
        "content": base64.b64encode(updated.encode()).decode(),
        "branch": "main"
    }
    if sha:
        payload["sha"] = sha
    r = requests.put(api, headers=headers, json=payload, timeout=10)
    if r.status_code in (200, 201):
        return jsonify({"status": "approved", "domain": domain})
    return jsonify({"status": "failed", "code": r.status_code}), 500

@app.route("/reject-skill", methods=["POST"])
def reject_skill():
    if not auth_required():
        return jsonify({"error": "Unauthorized"}), 401
    domain = request.json.get("domain", "")
    proposals = _load_proposals()
    proposals.pop(domain, None)
    _save_proposals(proposals)
    return jsonify({"status": "rejected"})


@app.route("/debug-env", methods=["GET"])
def debug_env():
    import os
    key = os.getenv("GROQ_KEY", "MISSING")
    return jsonify({"groq_key_length": len(key), "groq_key_prefix": key[:8] if key != "MISSING" else "MISSING"})


# ── OSINT endpoint ────────────────────────────────────────────────

@app.route("/osint", methods=["POST"])
def osint():
    if not auth_required():
        return jsonify({"error": "Unauthorized"}), 401
    data = request.json or {}
    query_type = data.get("type", "").strip().lower()
    query      = data.get("query", "").strip()
    modules    = data.get("modules", None)

    if not query_type or not query:
        return jsonify({"error": "Both type and query are required"}), 400

    from osint.dispatcher import dispatch
    result = dispatch(query_type, query, modules)

    if result.get("legal_block"):
        return jsonify(result), 403

    return jsonify(result)


@app.route("/debug-plan", methods=["POST"])
def debug_plan():
    if not auth_required():
        return jsonify({"error": "Unauthorized"}), 401
    data = request.json
    goal = data.get("goal", "").strip()
    import json, urllib.request
    groq_key = os.getenv("GROQ_KEY", "")
    PLAN_SYSTEM_PROMPT = """You are a task planner for a personal AI assistant.
Given a goal, break it into 2-5 concrete steps.
Each step must have:
- name: short label
- type: one of [search, scraping, automation, reasoning, notify]
- prompt: exact instruction for that step
- depends_on: index of step this depends on (-1 if none)

Return ONLY a JSON array. No explanation. No markdown."""
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
        headers={"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"}
    )
    try:
        res = urllib.request.urlopen(req, timeout=10)
        data = json.loads(res.read())
        raw = data["choices"][0]["message"]["content"].strip()
        return jsonify({"raw": raw})
    except Exception as e:
        return jsonify({"error": str(e)})


@app.route("/tasks", methods=["GET"])
def get_tasks():
    if not auth_required():
        return jsonify({"error": "Unauthorized"}), 401
    from planner import get_active_tasks
    tasks = get_active_tasks()
    return jsonify(tasks)


@app.route("/profile", methods=["GET"])
def get_profile_endpoint():
    if not auth_required():
        return jsonify({"error": "Unauthorized"}), 401
    from profile import get_profile, get_context_string
    return jsonify({
        "profile": get_profile(),
        "context": get_context_string()
    })


@app.route("/profile", methods=["POST"])
def update_profile_endpoint():
    if not auth_required():
        return jsonify({"error": "Unauthorized"}), 401
    data = request.json
    key = data.get("key", "")
    value = data.get("value", "")
    category = data.get("category", "personal")
    if not key or not value:
        return jsonify({"error": "key and value required"}), 400
    from profile import update_profile
    ok = update_profile(key, value, category)
    return jsonify({"updated": ok})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8003, debug=True)



# ── Task Planner endpoints ─────────────────────────────────────────

@app.route("/plan", methods=["POST"])
def plan():
    if not auth_required():
        return jsonify({"error": "Unauthorized"}), 401
    data = request.json
    goal = data.get("goal", "").strip()
    schedule = data.get("schedule", "manual")
    if not goal:
        return jsonify({"error": "goal required"}), 400

    from planner import plan_goal, save_task
    steps = plan_goal(goal, router)
    if not steps:
        return jsonify({"error": "Could not generate steps"}), 500

    task_id = save_task(goal, steps, schedule)
    return jsonify({
        "task_id": task_id,
        "goal": goal,
        "steps": steps,
        "schedule": schedule
    })


@app.route("/run-task", methods=["POST"])
def run_task():
    if not auth_required():
        return jsonify({"error": "Unauthorized"}), 401
    data = request.json
    task_id = data.get("task_id", "")
    if not task_id:
        return jsonify({"error": "task_id required"}), 400

    from planner import get_active_tasks, save_run, get_runs
    import urllib.request as _ur2

    # Find the task
    tasks = get_active_tasks()
    task = next((t for t in tasks if t["id"] == task_id), None)
    if not task:
        return jsonify({"error": "Task not found or inactive"}), 404

    # Reset completed runs if task is recurring and last_run was not today
    sb_url = os.getenv("SUPABASE_URL", "")
    sb_key = os.getenv("SUPABASE_KEY", "")
    last_run = task.get("last_run")
    should_reset = False
    if last_run:
        from datetime import date
        last_run_date = last_run[:10]
        today = date.today().isoformat()
        if last_run_date < today:
            should_reset = True
    else:
        should_reset = True

    if should_reset:
        try:
            _ur2.urlopen(
                _ur2.Request(
                    f"{sb_url}/rest/v1/task_runs?task_id=eq.{task_id}",
                    headers={
                        "apikey": sb_key,
                        "Authorization": f"Bearer {sb_key}",
                        "Content-Type": "application/json"
                    },
                    method="DELETE"
                ),
                timeout=8
            )
        except Exception as e:
            print(f"[run-task] reset failed: {e}")

    steps = task["steps"]
    previous_runs = get_runs(task_id)
    completed = {r["step_index"]: r["output"] for r in previous_runs if r["status"] == "done"}

    results = []

    for i, step in enumerate(steps):
        # Skip already completed steps
        if i in completed:
            results.append({"step": i, "name": step["name"], "status": "skipped", "output": completed[i]})
            continue

        # Check dependency
        depends_on = step.get("depends_on", -1)
        if depends_on != -1 and depends_on not in completed:
            save_run(task_id, i, step["name"], "blocked", error="dependency not met")
            results.append({"step": i, "name": step["name"], "status": "blocked"})
            continue

        # Inject previous step output into prompt if referenced
        prompt = step["prompt"]
        # Inject user context
        from profile import get_context_string
        ctx = get_context_string()
        if ctx:
            prompt = ctx + "\n\n" + prompt
        if depends_on != -1 and depends_on in completed:
            prompt = prompt.replace(f"{{step_{depends_on}_output}}", completed[depends_on])

        # Notify step — send to Telegram directly
        if step["type"] == "notify":
            token = os.getenv("TELEGRAM_BOT_TOKEN")
            chat_id = os.getenv("TELEGRAM_CHAT_ID")
            msg = prompt
            # Use last completed output as message if prompt is generic
            if "send" in prompt.lower() and completed:
                last = max(completed.keys())
                msg = f"Task: {task['goal']}\n\n{completed[last]}"
            if token and chat_id:
                import requests as req
                req.post(
                    f"https://api.telegram.org/bot{token}/sendMessage",
                    json={"chat_id": chat_id, "text": msg[:4000]},
                    timeout=10
                )
            output = "notified"
            completed[i] = output
            save_run(task_id, i, step["name"], "done", output=output)
            results.append({"step": i, "name": step["name"], "status": "done", "output": output})
            continue

        # All other step types — route through Nexus
        try:
            result = router.ask(prompt, task=step["type"])
            output = result.get("response", "")
            if not output or "All providers exhausted" in output:
                save_run(task_id, i, step["name"], "failed", error="provider exhausted")
                results.append({"step": i, "name": step["name"], "status": "failed"})
                continue
            completed[i] = output
            save_run(task_id, i, step["name"], "done", output=output)
            results.append({"step": i, "name": step["name"], "status": "done", "output": output[:300]})
        except Exception as e:
            save_run(task_id, i, step["name"], "failed", error=str(e))
            results.append({"step": i, "name": step["name"], "status": "failed", "error": str(e)})

    # Update last_run on task
    import urllib.request as _ur
    sb_url = os.getenv("SUPABASE_URL", "")
    sb_key = os.getenv("SUPABASE_KEY", "")
    _ur.urlopen(
        _ur.Request(
            f"{sb_url}/rest/v1/scheduled_tasks?id=eq.{task_id}",
            data=_json.dumps({"last_run": datetime.utcnow().isoformat()}).encode(),
            headers={
                "apikey": sb_key,
                "Authorization": f"Bearer {sb_key}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal"
            },
            method="PATCH"
        ),
        timeout=8
    )

    return jsonify({"task_id": task_id, "results": results})
