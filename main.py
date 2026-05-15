from flask import Flask, request, jsonify
from router import Router
import os 
import requests	 

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
    data = request.json
    result = router.ask(data["prompt"], data.get("task"))
    return jsonify(result)

@app.route("/search", methods=["POST"])
def search():
    data = request.json
    result = router.ask(data["query"], task="search")
    return jsonify(result)

@app.route("/image", methods=["POST"])
def image():
    data = request.json
    prompt = data.get("prompt")
    if not prompt:
        return jsonify({"error": "prompt required"}), 400
    try:
        result = router.generate_image(prompt)

        # Send to Telegram if no callback specified
        if not data.get("callback_url"):
            token = os.getenv("TELEGRAM_BOT_TOKEN")
            chat_id = os.getenv("TELEGRAM_CHAT_ID")
            if token and chat_id:
                if "image_b64" in result:
                    import base64
                    img_bytes = base64.b64decode(result["image_b64"])
                    requests.post(
                        f"https://api.telegram.org/bot{token}/sendPhoto",
                        data={"chat_id": chat_id},
                        files={"photo": ("image.jpg", img_bytes, "image/jpeg")}
                    )
                elif "image_url" in result:
                    requests.post(
                        f"https://api.telegram.org/bot{token}/sendPhoto",
                        data={"chat_id": chat_id, "photo": result["image_url"]}
                    )

        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8001, debug=True)
