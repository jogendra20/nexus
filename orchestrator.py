from rate_limiter import LimiterManager
from scorer import get_score

# Static quality scores per provider per task (0-10)
'''QUALITY_SCORES = {
    "github_models": {"reasoning": 10, "premium": 10, "coding": 9, "trading": 7, "search": 5, "default": 8},
    "nvidia":        {"reasoning": 9,  "premium": 9,  "coding": 8, "trading": 7, "search": 5, "default": 7},
    "cerebras":      {"reasoning": 6,  "premium": 5,  "coding": 6, "trading": 9, "search": 4, "default": 8},
    "gemini":        {"reasoning": 8,  "premium": 8,  "coding": 7, "trading": 8, "search": 8, "default": 8},
    "groq":          {"reasoning": 6,  "premium": 5,  "coding": 6, "trading": 8, "search": 5, "default": 7},
    "mistral":       {"reasoning": 6,  "premium": 6,  "coding": 10,"trading": 5, "search": 4, "default": 6},
    "openrouter":    {"reasoning": 7,  "premium": 7,  "coding": 7, "trading": 6, "search": 5, "default": 6},
    "drona":         {"reasoning": 2,  "premium": 2,  "coding": 2, "trading": 6, "search": 10,"default": 3},
    "huggingface":   {"reasoning": 7,  "premium": 6,  "coding": 7, "trading": 5, "search": 4, "default": 6},
}'''

# Weights
QUALITY_WEIGHT      = 0.6
AVAILABILITY_WEIGHT = 0.4

class Orchestrator:
    def __init__(self, limiter: LimiterManager):
        self.limiter = limiter

    def availability_score(self, provider: str) -> float:
        status = self.limiter.status()
        remaining = status.get(provider, 0)
        limits = {
            "github_models": 15,
            "nvidia":        40,
            "cerebras":      30,
            "gemini":        60,
            "groq":          30,
            "mistral":       30,
            "openrouter":    20,
            "drona":         100,
        }
        max_calls = limits.get(provider, 10)
        return min(remaining / max_calls, 1.0) * 10  # normalize to 0-10

    def rank(self, providers: list, task: str) -> list:
        scores = []
        for provider in providers:
            # Skip if rate limited
            if not self.limiter.check(provider):
                continue

            quality = get_score(provider, task)
            availability = self.availability_score(provider)
            final = (quality * QUALITY_WEIGHT) + (availability * AVAILABILITY_WEIGHT)

            scores.append({
                "provider": provider,
                "quality":  quality,
                "availability": round(availability, 2),
                "final":    round(final, 2),
            })

        # Sort by final score descending
        scores.sort(key=lambda x: x["final"], reverse=True)
        return scores
