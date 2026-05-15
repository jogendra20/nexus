import requests
import base64
from config import GEMINI_KEY

class GeminiProvider:
    MODELS = [
        "gemini-2.5-flash",
        "gemini-1.5-flash",
        "gemini-1.5-pro",
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

    def generate_image(self, prompt: str) -> dict:
        try:
            r = requests.post(
                "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent",
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
                        "model": "gemini-2.0-flash-exp",
                    }
            raise Exception("No image in response")
        except Exception as e:
            print(f"[Gemini Image] Failed: {e}")
            raise Exception(f"Gemini image failed: {e}")
