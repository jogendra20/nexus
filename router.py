from orchestrator import Orchestrator
from rate_limiter import LimiterManager
from config import TASK_KEYWORDS, TASK_ROUTES
from logger import log_request
from providers.gemini import GeminiProvider
from providers.openrouter import OpenRouterProvider
from providers.poe import PoeProvider
from providers.perplexity import PerplexityProvider
from providers.drona import DronaProvider
from providers.groq_provider import GroqProvider
from providers.nvidia import NvidiaProvider
from providers.cerebras import CerebrasProvider
from providers.mistral import MistralProvider
from providers.github_models import GitHubModelsProvider
from providers.huggingface import HuggingFaceProvider
from scorer import update_score
import time

class Router:
    def __init__(self):
        self.limiter = LimiterManager()
        self.orchestrator = Orchestrator(self.limiter)
        self.providers = {
            "gemini":        GeminiProvider(),
            "openrouter":    OpenRouterProvider(),
            "poe":           PoeProvider(),
            "perplexity":    PerplexityProvider(),
            "drona":         DronaProvider(),
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
        start = time.time()
        if not task:
            task = self.classify(prompt)

        candidates = TASK_ROUTES.get(task, TASK_ROUTES["default"])
        ranked = self.orchestrator.rank(candidates, task)

        for entry in ranked:
            provider = entry["provider"]
            try:
                if provider in ("openrouter", "groq", "nvidia", "cerebras", "mistral"):
                    response = self.providers[provider].ask(prompt, task)
                else:
                    response = self.providers[provider].ask(prompt)

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
        # Try HuggingFace FLUX first
        try:
            return self.providers["huggingface"].generate_image(prompt)
        except Exception as e:
            print(f"[Image] HF failed: {e} — falling back to Pollinations")
        # Fallback to Pollinations
        url = f"https://image.pollinations.ai/prompt/{prompt.replace(' ', '%20')}"
        return {
            "image_url": url,
            "provider": "pollinations",
            "model": "flux",
        }
