# Playwright & Stealth Automation Skill

## 1. Adaptive Stealth (Scrapling + Browserforge)
```python
from scrapling import Stealer
import os

def run():
    stealer = Stealer(headless=True)
    try:
        page = stealer.get("https://target-website.com")
        title = page.attrib("//h1", "text")
        print(f"Found: {title}")
    finally:
        stealer.quit()

if __name__ == "__main__":
    run()
from curl_cffi import requests

def run():
    response = requests.get(
        "https://api.target.com/data",
        impersonate="chrome120",
        headers={"Referer": "https://google.com"\}
    )
    print(response.text)

if __name__ == "__main__":
    run()
### 3. Update `orchestrator.py` (Smart Model Routing)
This makes Nexus automatically choose **GitHub Models** for any "Hard" automation tasks.

```bash
cat << 'EOF' > orchestrator.py
from rate_limiter import LimiterManager

class Orchestrator:
    def __init__(self, limiter: LimiterManager):
        self.limiter = limiter

    def rank(self, providers: list, task: str, difficulty: str = "easy") -> list:
        # Prioritize GitHub Models for Automation
        if task == "automation" and difficulty in ("medium", "hard"):
            if self.limiter.check("github_models"):
                return [{"provider": "github_models", "quality": 10, "final": 10}]
        
        # Fallback to standard ranking
        return [{"provider": "groq", "quality": 7, "final": 7}]

def get_score(provider, task):
    scores = {
        "github_models": {"automation": 10, "default": 8},
        "groq": {"automation": 6, "default": 7}
    }
    return scores.get(provider, {}).get(task, 5)
