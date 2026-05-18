"""
check_keys.py - Direct provider key test
"""
import os
import sys
sys.path.insert(0, '/data/data/com.termux/files/home/nexus')

from providers.groq_provider import GroqProvider
from providers.cerebras import CerebrasProvider
from providers.gemini import GeminiProvider
from providers.nvidia import NvidiaProvider
from providers.mistral import MistralProvider
from providers.github_models import GitHubModelsProvider
from providers.openrouter import OpenRouterProvider
from providers.huggingface import HuggingFaceProvider

PROVIDERS = {
    "groq":          (GroqProvider(),         "trading"),
    "cerebras":      (CerebrasProvider(),     "trading"),
    "gemini":        (GeminiProvider(),       None),
    "nvidia":        (NvidiaProvider(),       "reasoning"),
    "mistral":       (MistralProvider(),      "coding"),
    "github_models": (GitHubModelsProvider(), None),
    "openrouter":    (OpenRouterProvider(),   "default"),
    "huggingface":   (HuggingFaceProvider(),  None),
}

print("\n🔍 NEXUS Direct Provider Health Check\n")
for name, (provider, task) in PROVIDERS.items():
    try:
        if task:
            r = provider.ask("Reply with only: OK", task)
        else:
            r = provider.ask("Reply with only: OK")
        status = "✅" if r and len(r) < 50 else "⚠️ "
        print(f"  {status} {name:15} → {str(r)[:20]}")
    except Exception as e:
        print(f"  ❌ {name:15} → {str(e)[:50]}")

print("\nDone.")
