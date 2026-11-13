import os
import requests

class GitHubModelsProvider:
    def __init__(self):
        self.key = os.getenv("GITHUB_MODELS_KEY")
        self.url = "https://models.inference.ai.azure.com/chat/completions"
        self.models = ["gpt-4o", "o4-mini", "gpt-4.1"]

    def ask(self, prompt: str) -> str:
        raise RuntimeError(
            "GitHub Models API retired; migrate this route to an active provider"
        )
