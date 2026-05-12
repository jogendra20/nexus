from flask import Flask, request, jsonify
from router import Router

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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8001, debug=True)
