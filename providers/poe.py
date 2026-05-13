import requests
from config import POE_API_KEY

class PoeProvider:
    URL = "https://api.poe.com/v1/chat/completions"

    BOTS = {
        "default":   "claude-haiku-4.5",      # best cheap Claude
        "coding":    "gpt-5.1-codex-mini",    # coding specialized
        "reasoning": "o4-mini",               # reasoning specialized  
        "premium":   "Claude-Sonnet-4.6",     # save for important
        "fast":      "gemini-2.0-flash-lite", # fastest
        "search":    "gpt-4o-mini-search",    # has web search
    }

    def ask(self, prompt: str, bot: str = "default") -> str:
        if not POE_API_KEY:
            raise Exception("POE_API_KEY not set")

        model = self.BOTS.get(bot, self.BOTS["default"])
        r = requests.post(
            self.URL,
            headers={
                "Authorization": f"Bearer {POE_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=30
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
