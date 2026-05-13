import requests
from config import NVIDIA_KEY

class NvidiaProvider:
    URL = "https://integrate.api.nvidia.com/v1/chat/completions"

    MODELS = {
        "default":   "meta/llama-3.3-70b-instruct",
        "coding":    "deepseek-ai/deepseek-v4-flash",
        "reasoning": "openai/gpt-oss-120b",
        "fast":      "meta/llama-3.1-8b-instruct",
        "premium":   "openai/gpt-oss-120b",
    }

    def ask(self, prompt: str, task: str = "default") -> str:
        if not NVIDIA_KEY:
            raise Exception("NVIDIA_KEY not set")

        model = self.MODELS.get(task, self.MODELS["default"])
        r = requests.post(
            self.URL,
            headers={
                "Authorization": f"Bearer {NVIDIA_KEY}",
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
