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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8001, debug=True)
