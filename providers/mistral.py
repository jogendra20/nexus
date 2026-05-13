import requests
from config import MISTRAL_KEY

class MistralProvider:
    URL = "https://api.mistral.ai/v1/chat/completions"

    MODELS = {
        "default": "mistral-small-latest",
        "coding":  "codestral-latest",
        "fast":    "mistral-small-latest",
    }

    def ask(self, prompt: str, task: str = "default") -> str:
        if not MISTRAL_KEY:
            raise Exception("MISTRAL_KEY not set")

        model = self.MODELS.get(task, self.MODELS["default"])
        r = requests.post(
            self.URL,
            headers={
                "Authorization": f"Bearer {MISTRAL_KEY}",
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
