"""
telegram_bot.py - NEXUS Telegram Interface
Chat with NEXUS through Telegram.
"""

import os
import requests

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID")
BASE_URL  = f"https://api.telegram.org/bot{BOT_TOKEN}"

def send_message(chat_id: str, text: str):
    requests.post(
        f"{BASE_URL}/sendMessage",
        json={
            "chat_id":    chat_id,
            "text":       text,
            "parse_mode": "Markdown",
        },
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

def process_message(text: str, chat_id: str):
    """Route message to NEXUS and reply."""
    text = text.strip()

    # Commands
    if text.startswith("/start"):
        send_message(chat_id, "👋 *NEXUS Bot Online*\n\nCommands:\n`/ask <prompt>` — chat\n`/image <prompt>` — generate image\n`/search <query>` — search news\n`/status` — provider quotas\n\nOr just send any message to chat.")
        return

    if text.startswith("/status"):
        from router import Router
        r = Router()
        status = r.status()
        lines = ["📊 *NEXUS Provider Status*\n"]
        for provider, remaining in status.items():
            bar = "█" * min(int(remaining / 10), 10) + "░" * (10 - min(int(remaining / 10), 10))
            lines.append(f"`{provider:15}` {bar} {remaining}")
        send_message(chat_id, "\n".join(lines))
        return

    if text.startswith("/image "):
        prompt = text[7:].strip()
        send_message(chat_id, f"🎨 Generating image...")
        from router import Router
        r = Router()
        result = r.generate_image(prompt)
        if "image_b64" in result:
            send_photo(chat_id, image_b64=result["image_b64"], caption=f"_{prompt}_")
        elif "image_url" in result:
            send_photo(chat_id, image_url=result["image_url"], caption=f"_{prompt}_")
        return

    if text.startswith("/search "):
        query = text[8:].strip()
        send_message(chat_id, f"🔍 Searching...")
        from providers.search import SearchProvider
        sp = SearchProvider()
        data = sp.search(query, max_results=3, freshness="day")
        results = data.get("results", [])
        if not results:
            send_message(chat_id, "No results found.")
            return
        lines = [f"🔍 *{query}*\n"]
        for r in results[:3]:
            lines.append(f"• [{r['title']}]({r['url']})\n  _{r['source']}_")
        send_message(chat_id, "\n".join(lines))
        return

    if text.startswith("/ask "):
        prompt = text[5:].strip()
    else:
        prompt = text

    # Route to NEXUS
    send_message(chat_id, "⏳ Thinking...")
    from router import Router
    r = Router()
    result = r.ask(prompt)
    response = result.get("response", "No response")
    provider = result.get("provider", "unknown")

    # Truncate if too long
    if len(response) > 3800:
        response = response[:3800] + "...\n\n_[truncated]_"

    send_message(chat_id, f"{response}\n\n_via {provider}_")

def handle_update(update: dict):
    """Process incoming Telegram update."""
    message = update.get("message", {})
    text    = message.get("text", "")
    chat_id = str(message.get("chat", {}).get("id", ""))

    if not text or not chat_id:
        return

    # Security — only allow your chat ID
    if CHAT_ID and chat_id != CHAT_ID:
        send_message(chat_id, "⛔ Unauthorized.")
        return

    try:
        process_message(text, chat_id)
    except Exception as e:
        send_message(chat_id, f"❌ Error: {str(e)[:200]}")
