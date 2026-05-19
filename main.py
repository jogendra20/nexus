from flask import Flask, request, jsonify
from router import Router
from auth import auth_required
import os
import requests
import base64

app = Flask(__name__)
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
    result = router.ask(data["prompt"], data.get("task"), data.get("difficulty", "easy"))
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

    # Strip markdown fences if present
    import re
    code = re.sub(r"^```(?:python)?\n?|```$", "", code, flags=re.MULTILINE).strip()

    # Step 2: Push to GitHub
    from github_pusher import push_script, trigger_workflow
    push_result = push_script(code, filename)

    if not push_result["success"]:
        return jsonify({"error": "Push failed", "detail": push_result}), 500

    # Step 3: Trigger workflow
    trigger_result = trigger_workflow(push_result["filename"], prompt[:100])

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

    return jsonify({
        "code": code,
        "provider": provider,
        "file": push_result["filename"],
        "triggered": trigger_result["success"]
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
- If the error is JSONDecodeError or RemoteDisconnected on nseindia.com, switch to Tickertape API: https://api.tickertape.in/stocks/screener/filter\?sortBy\=change_percent\&sortOrder\=desc\&limit\=10
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

    trigger_result = trigger_workflow(push_result["filename"], f"[RETRY] {prompt[:80]}")

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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8003, debug=True)
