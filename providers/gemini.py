import requests
import base64
from config import GEMINI_KEY

class GeminiProvider:
    MODELS = [
    "gemini-3.8-flash",
    "gemini-3.5-flash-lite",
]

    def ask(self, prompt: str) -> str:
        last_error = None
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
                last_error = e
                continue
        raise last_error or Exception("All Gemini models failed")

    def generate_image(self, prompt: str) -> dict:
        try:
            r = requests.post(
                "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-image:generateContent",
                headers={
                    "x-goog-api-key": GEMINI_KEY,
                    "Content-Type": "application/json"
                },
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"responseModalities": ["IMAGE", "TEXT"]}
                },
                timeout=60
            )
            r.raise_for_status()
            parts = r.json()["candidates"][0]["content"]["parts"]
            for part in parts:
                if "inlineData" in part:
                    return {
                        "image_b64": part["inlineData"]["data"],
                        "provider": "gemini",
                        "model": "gemini-3.1-flash-image",
                    }
            raise Exception("No image in response")
        except Exception as e:
            print(f"[Gemini Image] Failed: {e}")
            raise Exception(f"Gemini image failed: {e}")
