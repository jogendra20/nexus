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

        AUTOMATION_CONTEXT = """You are a Python automation engineer. Output ONLY raw Python code. No explanations, no comments about what the code does, no markdown, no prose before or after.

Rules:
- Runtime: GitHub Actions Ubuntu 22.04, Python 3.11
- Available: playwright, requests, beautifulsoup4, pandas, lxml
- Playwright: always use --no-sandbox --disable-dev-shm-usage, headless=True
- Screenshots: always save as screenshot.png using page.screenshot(path="screenshot.png")
- Output: use print() for text results, save files for binary results
- NSE India: never use playwright on nseindia.com. Use requests + NSE JSON API with cookies
- No hardcoded secrets: use os.getenv()

CRITICAL: Your entire response must be valid Python. No prose. No explanations. Code only."""

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
