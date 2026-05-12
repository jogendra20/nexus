import requests
from config import GEMINI_KEY

class GeminiProvider:
    MODELS = [
        "gemini-2.5-flash",
        "gemini-1.5-flash",  # fallback
        "gemini-1.5-pro",    # last resort
    ]

    def ask(self, prompt: str) -> str:
        for model in self.MODELS:
            try:
                r = requests.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                    headers={
                        "x-goog-api-key": GEMINI_KEY,
                        "Content-Type": "application/json"
                    },
                    json={"contents": [{"parts": [{"text": prompt}]}]},
                    timeout=30
                )
                r.raise_for_status()
                return r.json()["candidates"][0]["content"]["parts"][0]["text"]
            except Exception as e:
                print(f"⚠️ Gemini {model} failed: {e}")
                continue
        raise Exception("All Gemini models failed")
