import requests
from config import PERPLEXITY_TOKEN

class PerplexityProvider:

    def ask(self, prompt: str) -> str:
        if not PERPLEXITY_TOKEN:
            raise Exception("PERPLEXITY_TOKEN not set")

        session = requests.Session()
        session.headers.update({
            "Cookie": f"__Secure-next-auth.session-token={PERPLEXITY_TOKEN}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Referer": "https://www.perplexity.ai/",
            "Origin": "https://www.perplexity.ai",
        })

        r = session.post(
            "https://www.perplexity.ai/api/ask",
            json={
                "query": prompt,
                "search_focus": "internet",
                "language": "en-US",
            },
            timeout=30
        )
        r.raise_for_status()
        return r.json().get("answer", r.text[:500])
