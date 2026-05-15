import os
import requests
import base64

HF_TOKEN = os.getenv("HF_TOKEN")

class HuggingFaceProvider:
    IMAGE_MODELS = [
        "black-forest-labs/FLUX.1-schnell",  # fastest
        "black-forest-labs/FLUX.1-dev",      # quality
        "stabilityai/stable-diffusion-3.5-large",  # fallback
    ]

    TEXT_MODELS = [
    "meta-llama/Llama-3.3-70B-Instruct:fastest",
    "deepseek-ai/DeepSeek-R1:fastest",
    "Qwen/Qwen2.5-72B-Instruct:fastest",
   ]

    def ask(self, prompt: str) -> str:
        for model in self.TEXT_MODELS:
            try:
                r = requests.post(
    "https://router.huggingface.co/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {HF_TOKEN}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": 1000,
                    },
                    timeout=60,
                )
                r.raise_for_status()
                return r.json()["choices"][0]["message"]["content"]
            except Exception as e:
                print(f"⚠️ HF {model} failed: {e}")
                continue
        raise Exception("All HuggingFace text models failed")

    def generate_image(self, prompt: str) -> dict:
        for model in self.IMAGE_MODELS:
            try:
                r = requests.post(
                    f"https://router.huggingface.co/hf-inference/models/{model}",
                    headers={
                        "Authorization": f"Bearer {HF_TOKEN}",
                        "Content-Type": "application/json",
                    },
                    json={"inputs": prompt},
                    timeout=120,
                )
                r.raise_for_status()
                b64 = base64.b64encode(r.content).decode("utf-8")
                return {
                    "image_b64": b64,
                    "provider": "huggingface",
                    "model": model,
                }
            except Exception as e:
                print(f"⚠️ HF Image {model} failed: {e}")
                continue
        raise Exception("All HuggingFace image models failed")
