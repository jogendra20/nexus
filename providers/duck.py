import requests
import json

class DuckProvider:

    MODELS = {
        "default":   "gpt-4o-mini",
        "coding":    "o3-mini",
        "reasoning": "o3-mini",
        "claude":    "claude-3-haiku",
        "llama":     "llama-3.3-70b",
        "mistral":   "mistral-small-3",
    }

    def _get_vqd(self) -> str:
        """Get VQD token — DuckDuckGo's session token"""
        r = requests.get(
            "https://duckduckgo.com/duckchat/v1/status",
            headers={
                "User-Agent": "Mozilla/5.0",
                "x-vqd-accept": "1"
            },
            timeout=10
        )
        return r.headers.get("x-vqd-4", "")

    def ask(self, prompt: str, bot: str = "default") -> str:
        model = self.MODELS.get(bot, self.MODELS["default"])
        vqd = self._get_vqd()

        r = requests.post(
            "https://duckduckgo.com/duckchat/v1/chat",
            headers={
                "User-Agent": "Mozilla/5.0",
                "Content-Type": "application/json",
                "x-vqd-4": vqd,
            },
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=30
        )
        r.raise_for_status()

        # Parse streaming response
        full_response = ""
        for line in r.text.split("\n"):
            if line.startswith("data: "):
                data = line[6:]
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                    full_response += chunk.get("message", "")
                except Exception:
                    continue

        return full_response
