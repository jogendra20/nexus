"""
telegram_bot.py - NEXUS Multi-Agent Telegram Interface
Simple questions → one agent, fast.
Hard questions → multiple agents collaborate.
"""

import os
import re
import requests

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# ── Conversation memory ───────────────────────────────────────────
_memory = {}  # chat_id -> list of {role, content}
_MEMORY_LIMIT = 10  # last 10 exchanges

def get_history(chat_id: str) -> list:
    return _memory.get(chat_id, [])

def add_to_history(chat_id: str, role: str, content: str):
    if chat_id not in _memory:
        _memory[chat_id] = []
    _memory[chat_id].append({"role": role, "content": content})
    # Keep only last N exchanges
    if len(_memory[chat_id]) > _MEMORY_LIMIT * 2:
        _memory[chat_id] = _memory[chat_id][-(_MEMORY_LIMIT * 2):]

def clear_history(chat_id: str):
    _memory[chat_id] = []
    
CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID")
BASE_URL  = f"https://api.telegram.org/bot{BOT_TOKEN}"

AGENT_ICONS = {
    "cerebras":      "⚡",
    "groq":          "🚀",
    "gemini":        "✨",
    "nvidia":        "🧠",
    "github_models": "🔮",
    "mistral":       "💻",
    "openrouter":    "🌐",
    "huggingface":   "🤗",
    "search":        "🔍",
}

AGENT_NAMES = {
    "cerebras":      "Cerebras",
    "groq":          "Groq",
    "gemini":        "Gemini",
    "nvidia":        "NVIDIA",
    "github_models": "GPT",
    "mistral":       "Mistral",
    "openrouter":    "OpenRouter",
    "huggingface":   "HuggingFace",
    "search":        "Search",
}

# ── Telegram helpers ──────────────────────────────────────────────
def send(chat_id: str, text: str):
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

# ── Intent detection ──────────────────────────────────────────────
def detect_intent(text: str) -> str:
    t = text.lower()

    # Image
    if any(w in t for w in [
        "draw ", "image of", "picture of", "photo of",
        "generate image", "create image", "show me a picture",
        "make an image", "paint ", "illustrate"
    ]):
        return "image"

    # Search
    if any(w in t for w in [
        "latest news", "today news", "current news",
        "what happened", "nifty today", "sensex today",
        "market today", "breaking news", "recent news"
    ]):
        return "search"

    # Code
    if any(w in t for w in [
        "write code", "write a function", "write a script",
        "code for", "implement ", "program to", "python code",
        "javascript code", "debug this", "fix this code",
        "def ", "function ", "class "
    ]):
        return "code"

    return "chat"

# ── Complexity detection ──────────────────────────────────────────
def is_complex(text: str) -> bool:
    t = text.lower()
    word_count = len(text.split())

    # Simple signals
    simple_starters = [
        "what is", "what are", "who is", "when is",
        "define ", "meaning of", "full form of",
        "how much", "how many", "what does",
    ]
    if any(t.startswith(s) for s in simple_starters) and word_count < 8:
        return False

    # Complex signals
    complex_signals = [
        "explain", "analyze", "compare", "difference between",
        "how does", "why does", "deep dive", "in detail",
        "comprehensive", "thorough", "elaborate", "breakdown",
        "strategy", "framework", "architecture", "design",
        "pros and cons", "advantages", "disadvantages",
        "step by step", "how to build", "how to implement",
    ]
    if any(s in t for s in complex_signals):
        return True

    # Long questions are complex
    if word_count > 15:
        return True

    return False

# ── Format response text ──────────────────────────────────────────
def format_response(text: str) -> str:
    # Convert markdown headers to bold
    text = re.sub(r'^#{1,3}\s+(.+)$', r'*\1*', text, flags=re.MULTILINE)

    # Keep code blocks
    text = re.sub(r'```(\w+)?\n', r'```\n', text)

    # Convert **bold** to *bold* (Telegram uses single *)
    text = re.sub(r'\*\*(.+?)\*\*', r'*\1*', text)

    # Clean excessive newlines
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()

# ── Agent message header ──────────────────────────────────────────
def agent_header(provider: str) -> str:
    icon = AGENT_ICONS.get(provider, "🤖")
    name = AGENT_NAMES.get(provider, provider.title())
    return f"{icon} *{name}*"

# ── Single agent response ─────────────────────────────────────────
def single_agent(text: str, chat_id: str, router, task: str = "default"):
    # Build memory-aware prompt
    history = get_history(chat_id)
    if history:
        context = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in history[-6:]])
        prompt = f"Previous conversation:\n{context}\n\nUSER: {text}"
    else:
        prompt = text

    add_to_history(chat_id, "user", text)
    result   = router.ask(prompt, task=task)
    response = result.get("response", "No response")
    provider = result.get("provider", "unknown")
    add_to_history(chat_id, "assistant", response[:300])

    formatted = format_response(response)
    if len(formatted) > 3800:
        formatted = formatted[:3800] + "\n\n_[truncated]_"

    send(chat_id, f"{agent_header(provider)}\n\n{formatted}")

# ── Multi agent response ──────────────────────────────────────────
def multi_agent(text: str, chat_id: str, router):
    send(chat_id, "🤝 *Agents collaborating...*")

    # Agent 1 — fast reasoning (cerebras/groq)
    result1   = router.ask(text, task="trading" if "trading" in text.lower() else "reasoning")
    response1 = result1.get("response", "")
    provider1 = result1.get("provider", "unknown")

    if response1:
        formatted1 = format_response(response1)
        if len(formatted1) > 1800:
            formatted1 = formatted1[:1800] + "..."
        send(chat_id, f"{agent_header(provider1)}\n\n{formatted1}")

    # Agent 2 — deeper model (nvidia/github_models)
    result2   = router.ask(
        f"Add important insights or corrections to this analysis of '{text}':\n\n{response1[:500]}",
        task="premium"
    )
    response2 = result2.get("response", "")
    provider2 = result2.get("provider", "unknown")

    if response2 and provider2 != provider1:
        formatted2 = format_response(response2)
        if len(formatted2) > 1800:
            formatted2 = formatted2[:1800] + "..."
        send(chat_id, f"{agent_header(provider2)}\n\n{formatted2}")

    # Synthesis — conclusion
    synthesis_prompt = f"""Based on these two analyses about '{text}':

Agent 1: {response1[:400]}
Agent 2: {response2[:400]}

Give a clear, concise final conclusion in 3-5 bullet points."""

    result3   = router.ask(synthesis_prompt, task="reasoning")
    response3 = result3.get("response", "")
    provider3 = result3.get("provider", "unknown")

    if response3:
        formatted3 = format_response(response3)
        send(chat_id,
            f"━━━━━━━━━━━━━━━━\n"
            f"🎯 *Conclusion*\n"
            f"━━━━━━━━━━━━━━━━\n\n"
            f"{formatted3}"
        )

# ── Code response ─────────────────────────────────────────────────
def code_agent(text: str, chat_id: str, router):
    result   = router.ask(text, task="coding")
    response = result.get("response", "")
    provider = result.get("provider", "unknown")

    formatted = format_response(response)
    if len(formatted) > 3800:
        formatted = formatted[:3800] + "\n\n_[truncated]_"

    send(chat_id, f"{agent_header(provider)}\n\n{formatted}")

# ── Main message processor ────────────────────────────────────────
def process_message(text: str, chat_id: str):
    text = text.strip()

    # Hard commands
    # Recon approvals
    if text.lower().startswith("approve skill "):
        domain = text[14:].strip()
        nexus_url = os.getenv("NEXUS_URL", "http://localhost:8003")
        nexus_key = os.getenv("NEXUS_API_KEY", "")
        import json as _j, urllib.request as _ur, time as _t
        send(chat_id, f"⏳ Approving `{domain}`...")
        for attempt in range(3):
            try:
                payload = _j.dumps({"domain": domain}).encode()
                req = _ur.Request(f"{nexus_url}/approve-skill", data=payload,
                    headers={"Content-Type":"application/json","X-API-Key":nexus_key})
                _ur.urlopen(req, timeout=35)
                send(chat_id, f"✅ approved — `{domain}` added to skill file")
                break
            except Exception as e:
                if attempt < 2:
                    send(chat_id, f"⏳ Render waking up, retry {attempt+1}/3...")
                    _t.sleep(15)
                else:
                    send(chat_id, f"❌ approve failed after 3 attempts: {e}")
        return

    if text.lower().startswith("reject skill "):
        domain = text[13:].strip()
        nexus_url = os.getenv("NEXUS_URL", "http://localhost:8003")
        nexus_key = os.getenv("NEXUS_API_KEY", "")
        import json as _j, urllib.request as _ur, time as _t
        for attempt in range(3):
            try:
                payload = _j.dumps({"domain": domain}).encode()
                req = _ur.Request(f"{nexus_url}/reject-skill", data=payload,
                    headers={"Content-Type":"application/json","X-API-Key":nexus_key})
                _ur.urlopen(req, timeout=35)
                send(chat_id, f"✅ rejected — `{domain}` skipped")
                break
            except Exception as e:
                if attempt < 2:
                    _t.sleep(15)
                else:
                    send(chat_id, f"❌ reject failed after 3 attempts: {e}")
        return

    if text.lower().startswith("approve "):

        site_key = text[8:].strip()
        nexus_url = os.getenv("NEXUS_URL", "http://localhost:8003")
        nexus_key = os.getenv("NEXUS_API_KEY", "")
        try:
            import json as _j, urllib.request as _ur
            payload = _j.dumps({"site_key": site_key}).encode()
            req = _ur.Request(f"{nexus_url}/approve-recon", data=payload,
                headers={"Content-Type":"application/json","X-API-Key":nexus_key})
            _ur.urlopen(req, timeout=10)
            send(chat_id, f"approved {site_key} - skill updated")
        except Exception as e:
            send(chat_id, f"approve failed: {e}")
        return

    if text.lower().startswith("reject "):
        site_key = text[7:].strip()
        nexus_url = os.getenv("NEXUS_URL", "http://localhost:8003")
        nexus_key = os.getenv("NEXUS_API_KEY", "")
        try:
            import json as _j, urllib.request as _ur
            payload = _j.dumps({"site_key": site_key}).encode()
            req = _ur.Request(f"{nexus_url}/reject-recon", data=payload,
                headers={"Content-Type":"application/json","X-API-Key":nexus_key})
            _ur.urlopen(req, timeout=10)
            send(chat_id, f"rejected {site_key} - keeping old selectors")
        except Exception as e:
            send(chat_id, f"reject failed: {e}")
        return

    if text == "/clear":
        clear_history(chat_id)
        send(chat_id, "🧹 Memory cleared.")
        return

    if text == "/start":

        send(chat_id,
            "👋 *NEXUS Online*\n\n"
            "I route your questions to the best AI agents.\n\n"
            "Simple question → ⚡ instant answer\n"
            "Hard question → 🤝 multiple agents\n"
            "Code request → 💻 code blocks\n"
            "Image request → 🎨 generated image\n"
            "News request → 🔍 live search\n\n"
            "Just talk naturally."
        )
        return

    if text == "/status":
        from router import Router
        r = Router()
        status = r.status()
        lines = ["📊 *Provider Status*\n"]
        for provider, remaining in status.items():
            filled = min(int(remaining / 10), 10)
            bar    = "█" * filled + "░" * (10 - filled)
            icon   = AGENT_ICONS.get(provider, "🤖")
            lines.append(f"{icon} `{provider:14}` {bar} {remaining}")
        send(chat_id, "\n".join(lines))
        return

    from router import Router
    router = Router()

    intent = detect_intent(text)

    if intent == "image":
        send(chat_id, "🎨 *Generating image...*")
        result = router.generate_image(text)
        if "image_b64" in result:
            send_photo(chat_id, image_b64=result["image_b64"], caption=text[:100])
        elif "image_url" in result:
            send_photo(chat_id, image_url=result["image_url"], caption=text[:100])
        return

    if intent == "search":
        send(chat_id, "🔍 *Searching live...*")
        from providers.search import SearchProvider
        sp      = SearchProvider()
        data    = sp.search(text, max_results=4, freshness="day")
        results = data.get("results", [])
        if not results:
            send(chat_id, "No results found.")
            return
        lines = ["🔍 *Live Results*\n"]
        for r in results[:4]:
            title   = r.get("title", "")[:60]
            url     = r.get("url", "")
            source  = r.get("source", "")
            snippet = r.get("snippet", "")[:80]
            lines.append(f"• [{title}]({url})\n  _{source}_ — {snippet}...")
        send(chat_id, "\n".join(lines))
        return

    if intent == "code":
        code_agent(text, chat_id, router)
        return

    # Chat — check complexity
    if is_complex(text):
        multi_agent(text, chat_id, router)
    else:
        single_agent(text, chat_id, router)

# ── Webhook handler ───────────────────────────────────────────────
def handle_update(update: dict):
    message = update.get("message", {})
    text    = message.get("text", "")
    chat_id = str(message.get("chat", {}).get("id", ""))

    if not text or not chat_id:
        return

    if CHAT_ID and chat_id != CHAT_ID:
        send(chat_id, "⛔ Unauthorized.")
        return

    try:
        process_message(text, chat_id)
    except Exception as e:
        send(chat_id, f"❌ Error: `{str(e)[:200]}`")
