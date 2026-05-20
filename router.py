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

    def ask(self, prompt: str, task: str = None, difficulty: str = "easy") -> dict:
        # Detect image requests
        if any(kw in prompt.lower() for kw in IMAGE_KEYWORDS):
            return self.generate_image(prompt)

        start = time.time()
        if not task:
            task = self.classify(prompt)

        candidates = TASK_ROUTES.get(task, TASK_ROUTES["default"])
        ranked = self.orchestrator.rank(candidates, task, difficulty)

        from main import get_skills
        _skills = get_skills()
        AUTOMATION_CONTEXT = f"""CRITICAL RULES — READ BEFORE WRITING ANY CODE:
1. ALWAYS use Playwright for ALL tasks. Never use requests, urllib, or httpx to fetch web pages.
2. Playwright is the only allowed HTTP client. No exceptions.
3. Output ONLY raw Python code. No explanations. No markdown. No prose.

You are a Python automation engineer.

Environment:
- Runtime: GitHub Actions Ubuntu 22.04, Python 3.11
- Available: playwright, beautifulsoup4, pandas
- Playwright: always use --no-sandbox --disable-dev-shm-usage, headless=True
- Screenshots: always save as screenshot.png using page.screenshot(path="screenshot.png")
- Output: use print() for text results, save files for binary results
- No hardcoded secrets: use os.getenv()

## REFERENCE SKILLS (use these exact patterns):
{_skills}

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
        try:
            result = self.providers["huggingface"].generate_image(prompt)
            result["provider"] = "huggingface"
            return result
        except Exception as e:
            print(f"[Image] HF failed: {e} — falling back to Pollinations")
            import urllib.parse
            url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}"
            return {"image_url": url, "provider": "pollinations", "model": "flux"}
