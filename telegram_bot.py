"""
telegram_bot.py - NEXUS Telegram Interface
Uses NEXUS itself to classify intent before routing.
"""

import os
import requests

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID")
BASE_URL  = f"https://api.telegram.org/bot{BOT_TOKEN}"

def send_message(chat_id: str, text: str):
    requests.post(
        f"{BASE_URL}/sendMessage",
        json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
        timeout=10,
    )

def send_photo(chat_id: str, image_b64: str = None, image_url: str = None, caption: str = ""):
    import base64
    if image_b64:
        img_bytes = base64.b64decode(image_b64)
        requests.post(
            f"{BASE_URL}/sendPhoto",
            data={"chat_id": chat_id, "caption": caption},
            files={"photo": ("image.jpg", img_bytes, "image/jpeg")},
            timeout=30,
        )
    elif image_url:
        requests.post(
            f"{BASE_URL}/sendPhoto",
            json={"chat_id": chat_id, "photo": image_url, "caption": caption},
            timeout=30,
        )

def classify_intent(text: str, router) -> str:
    """Use NEXUS to classify user intent."""
    prompt = f"""Classify this message into exactly one intent. Reply with only the intent word.

Intents:
- image: user wants to generate, create, draw, or see an image/picture/photo
- search: user wants news, current events, latest information, market data
- status: user wants to check system status or provider quotas
- chat: anything else — questions, conversation, analysis, coding, trading

Message: "{text}"

Reply with only: image, search, status, or chat"""

    result = router.ask(prompt, task="reasoning")
    intent = result.get("response", "chat").strip().lower()

    # Normalize
    if "image" in intent:   return "image"
    if "search" in intent:  return "search"
    if "status" in intent:  return "status"
    return "chat"

def process_message(text: str, chat_id: str):
    text = text.strip()

    # Hard commands
    if text.startswith("/start"):
        send_message(chat_id,
            "👋 *NEXUS Bot Online*\n\n"
            "Just talk naturally:\n"
            "• Ask anything → AI answers\n"
            "• Ask for an image → generates one\n"
            "• Ask for news → searches live\n"
            "• `/status` → provider quotas\n\n"
            "_Powered by NEXUS — 8 AI providers_"
        )
        return

    if text.startswith("/status"):
        from router import Router
        r = Router()
        status = r.status()
        lines = ["📊 *NEXUS Provider Status*\n"]
        for provider, remaining in status.items():
            filled = min(int(remaining / 10), 10)
            bar = "█" * filled + "░" * (10 - filled)
            lines.append(f"`{provider:15}` {bar} {remaining}")
        send_message(chat_id, "\n".join(lines))
        return

    # Load router once
    from router import Router
    router = Router()

    # Classify intent via NEXUS
    send_message(chat_id, "⏳ Processing...")
    intent = classify_intent(text, router)

    if intent == "image":
        send_message(chat_id, "🎨 Generating image...")
        result = router.generate_image(text)
        if "image_b64" in result:
            send_photo(chat_id, image_b64=result["image_b64"], caption=f"_{text[:100]}_")
        elif "image_url" in result:
            send_photo(chat_id, image_url=result["image_url"], caption=f"_{text[:100]}_")
        return

    if intent == "search":
        from providers.search import SearchProvider
        sp = SearchProvider()
        data = sp.search(text, max_results=3, freshness="day")
        results = data.get("results", [])
        if not results:
            send_message(chat_id, "No results found.")
            return
        lines = [f"🔍 *Search Results*\n"]
        for r in results[:3]:
            lines.append(f"• [{r['title']}]({r['url']})\n  _{r.get('source','')}_ — {r.get('snippet','')[:80]}...")
        send_message(chat_id, "\n".join(lines))
        return

    # Default — chat
    result = router.ask(text)
    response = result.get("response", "No response")
    provider = result.get("provider", "unknown")

    if len(response) > 3800:
        response = response[:3800] + "...\n\n_[truncated]_"

    send_message(chat_id, f"{response}\n\n_via {provider}_")

def handle_update(update: dict):
    message = update.get("message", {})
    text    = message.get("text", "")
    chat_id = str(message.get("chat", {}).get("id", ""))

    if not text or not chat_id:
        return

    if CHAT_ID and chat_id != CHAT_ID:
        send_message(chat_id, "⛔ Unauthorized.")
        return

    try:
        process_message(text, chat_id)
    except Exception as e:
        send_message(chat_id, f"❌ Error: {str(e)[:200]}")
