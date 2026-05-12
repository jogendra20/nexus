import requests
from config import GROQ_KEY

class GroqProvider:
    """
    Groq — last resort fallback for all tasks.
    Fastest inference. Already proven in ARJUN.
    """
    URL = "https://api.groq.com/openai/v1/chat/completions"

    MODELS = {
    "coding":  "llama-3.3-70b-versatile",
    "default": "llama-3.1-8b-instant",
}

    def ask(self, prompt: str, task: str = "default") -> str:
        if not GROQ_KEY:
            raise Exception("GROQ_KEY not set")

        model = self.MODELS.get(task, self.MODELS["default"])
        r = requests.post(
            self.URL,
            headers={"Authorization": f"Bearer {GROQ_KEY}"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=30
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
