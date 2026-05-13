import requests
from config import CEREBRAS_KEY

class CerebrasProvider:
    URL = "https://api.cerebras.ai/v1/chat/completions"

    MODELS = {
        "default": "llama-3.1-8b",
        "fast":    "llama-3.1-8b",
        "premium": "llama-3.3-70b",
    }

    def ask(self, prompt: str, task: str = "default") -> str:
        if not CEREBRAS_KEY:
            raise Exception("CEREBRAS_KEY not set")

        model = self.MODELS.get(task, self.MODELS["default"])
        r = requests.post(
            self.URL,
            headers={
                "Authorization": f"Bearer {CEREBRAS_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 1024
            },
            timeout=30
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
