from config import TASK_KEYWORDS, TASK_ROUTES
from rate_limiter import LimiterManager
from providers.gemini import GeminiProvider
from providers.openrouter import OpenRouterProvider
from providers.poe import PoeProvider
from providers.perplexity import PerplexityProvider
from providers.drona import DronaProvider
from providers.groq_provider import GroqProvider

class Router:
    def __init__(self):
        self.limiter = LimiterManager()
        self.providers = {
            "gemini":      GeminiProvider(),
            "openrouter":  OpenRouterProvider(),
            "poe":         PoeProvider(),
            "perplexity":  PerplexityProvider(),
            "drona":       DronaProvider(),
            "groq":        GroqProvider(),
        }

    def classify(self, prompt: str) -> str:
        prompt_lower = prompt.lower()
        for task, keywords in TASK_KEYWORDS.items():
            if any(kw in prompt_lower for kw in keywords):
                return task
        return "default"

    def ask(self, prompt: str, task: str = None) -> dict:
        if not task:
            task = self.classify(prompt)

        providers = TASK_ROUTES.get(task, TASK_ROUTES["default"])

        for provider in providers:
            if not self.limiter.check(provider):
                print(f"⚠️ {provider} rate limited — skipping")
                continue
            try:
                if provider in ("openrouter", "groq"):
                    response = self.providers[provider].ask(prompt, task)
                else:
                    response = self.providers[provider].ask(prompt)

                print(f"✅ {provider} responded")
                return {
                    "response": response,
                    "provider": provider,
                    "task": task
                }
            except Exception as e:
                print(f"⚠️ {provider} failed: {e} — trying next")
                continue

        return {
            "response": "All providers exhausted",
            "provider": None,
            "task": task
        }

    def status(self) -> dict:
        return self.limiter.status()
