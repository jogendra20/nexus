import requests
from config import CEREBRAS_KEY

class CerebrasProvider:
    URL = "https://api.cerebras.ai/v1/chat/completions"

    MODELS = {
        "default": "gpt-oss-120b",
        "fast":    "qwen-3.8-27b",
        "premium": "gpt-oss-120b",
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
