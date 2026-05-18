from flask import Flask, request, jsonify
from router import Router
from auth import auth_required
import os
import requests
import base64

app = Flask(__name__)
router = Router()

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
    result = router.ask(data["prompt"], data.get("task"))
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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8001, debug=True)
