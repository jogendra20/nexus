from orchestrator import Orchestrator
from rate_limiter import LimiterManager
from config import TASK_KEYWORDS, TASK_ROUTES
from logger import log_request
from providers.gemini import GeminiProvider
from providers.openrouter import OpenRouterProvider
from providers.poe import PoeProvider
from providers.perplexity import PerplexityProvider
from providers.search import SearchProvider
from providers.groq_provider import GroqProvider
from providers.nvidia import NvidiaProvider
from providers.cerebras import CerebrasProvider
from providers.mistral import MistralProvider
from providers.github_models import GitHubModelsProvider
from providers.huggingface import HuggingFaceProvider
from scorer import update_score
import time

IMAGE_KEYWORDS = ["generate image", "create image", "draw", "make image", "imagine"]

class Router:
    def __init__(self):
        self.limiter = LimiterManager()
        self.orchestrator = Orchestrator(self.limiter)
        self.providers = {
            "gemini":        GeminiProvider(),
            "openrouter":    OpenRouterProvider(),
            "poe":           PoeProvider(),
            "perplexity":    PerplexityProvider(),
            "search":        SearchProvider(),
            "groq":          GroqProvider(),
            "nvidia":        NvidiaProvider(),
            "cerebras":      CerebrasProvider(),
            "mistral":       MistralProvider(),
            "github_models": GitHubModelsProvider(),
            "huggingface":   HuggingFaceProvider(),
        }

    def classify(self, prompt: str) -> str:
        prompt_lower = prompt.lower()
        for task, keywords in TASK_KEYWORDS.items():
            if any(kw in prompt_lower for kw in keywords):
                return task
        return "default"

    def ask(self, prompt: str, task: str = None) -> dict:
        # Detect image requests
        if any(kw in prompt.lower() for kw in IMAGE_KEYWORDS):
            return self.generate_image(prompt)

        start = time.time()
        if not task:
            task = self.classify(prompt)

        candidates = TASK_ROUTES.get(task, TASK_ROUTES["default"])
        ranked = self.orchestrator.rank(candidates, task)

        AUTOMATION_CONTEXT = """You are generating Python automation code for this environment:
- Runtime: GitHub Actions Ubuntu 22.04
- Python: 3.11
- Libraries: playwright, scrapling
- Chromium flags: --no-sandbox --disable-dev-shm-usage
- Headless: True always
- Output: ONLY use print() for results. Never write files.
- No hardcoded secrets; use os.getenv()
Write complete, runnable code only. No explanations unless asked."""

        for entry in ranked:
            provider = entry["provider"]
            try:
                actual_prompt = f"{AUTOMATION_CONTEXT}\n\nTask: {prompt}" if task == "automation" else prompt
                if provider in ("openrouter", "groq", "nvidia", "cerebras", "mistral"):
                    response = self.providers[provider].ask(actual_prompt, task)
                else:
                    response = self.providers[provider].ask(actual_prompt)

                elapsed = int((time.time() - start) * 1000)
                update_score(
                    provider=provider,
                    task=task,
                    success=True,
                    response_time_ms=elapsed,
                    response_length=len(response),
                )
                log_request(
                    prompt=prompt,
                    task=task,
                    provider=provider,
                    scores=entry,
                    success=True,
                    response_time_ms=elapsed,
                )
                print(f"✅ {provider} responded | scores: {entry}")
                return {
                    "response": response,
                    "provider": provider,
                    "task": task,
                    "scores": entry,
                }
            except Exception as e:
                update_score(
                    provider=provider,
                    task=task,
                    success=False,
                )
                log_request(
                    prompt=prompt,
                    task=task,
                    provider=provider,
                    success=False,
                    error=str(e),
                )
                print(f"⚠️ {provider} failed: {e} — trying next")
                continue

        return {
            "response": "All providers exhausted",
            "provider": None,
            "task": task
        }

    def status(self) -> dict:
        return self.limiter.status()

    def generate_image(self, prompt: str) -> dict:
        import requests as req, base64, os
        token   = os.getenv("TELEGRAM_BOT_TOKEN")
        chat_id = os.getenv("TELEGRAM_CHAT_ID")

        try:
            result = self.providers["huggingface"].generate_image(prompt)
        except Exception as e:
            print(f"[Image] HF failed: {e} — falling back to Pollinations")
            url = f"https://image.pollinations.ai/prompt/{prompt.replace(' ', '%20')}"
            result = {"image_url": url, "provider": "pollinations", "model": "flux"}

        # Send to Telegram
        if token and chat_id:
            try:
                if "image_b64" in result:
                    img_bytes = base64.b64decode(result["image_b64"])
                    req.post(
                        f"https://api.telegram.org/bot{token}/sendPhoto",
                        data={"chat_id": chat_id},
                        files={"photo": ("image.jpg", img_bytes, "image/jpeg")}
                    )
                elif "image_url" in result:
                    req.post(
                        f"https://api.telegram.org/bot{token}/sendPhoto",
                        data={"chat_id": chat_id, "photo": result["image_url"]}
                    )
                print("[Image] Sent to Telegram")
            except Exception as e:
                print(f"[Image] Telegram send failed: {e}")

        return result
