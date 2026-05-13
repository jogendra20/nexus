import os
import requests

class GitHubModelsProvider:
    def __init__(self):
        self.key = os.getenv("GITHUB_MODELS_KEY")
        self.url = "https://models.inference.ai.azure.com/chat/completions"
        self.models = ["gpt-4o", "o4-mini", "gpt-4.1"]

    def ask(self, prompt: str) -> str:
        for model in self.models:
            try:
                response = requests.post(
                    self.url,
                    headers={
                        "Authorization": f"Bearer {self.key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": 1000,
                    },
                    timeout=30,
                )
                data = response.json()
                return data["choices"][0]["message"]["content"]
            except Exception as e:
                continue
        raise Exception("All GitHub Models failed")
