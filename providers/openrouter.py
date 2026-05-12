import requests
from config import OPENROUTER_KEY

class OpenRouterProvider:
    URL = "https://openrouter.ai/api/v1/chat/completions"

    MODELS = {
        "coding":  "openrouter/free",
        "default": "openrouter/free",
    }

    def ask(self, prompt: str, task: str = "default") -> str:
        model = self.MODELS.get(task, self.MODELS["default"])
        r = requests.post(
            self.URL,
            headers={
                "Authorization": f"Bearer {OPENROUTER_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/nexus",
                "X-Title": "NEXUS"
            },
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=30
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
