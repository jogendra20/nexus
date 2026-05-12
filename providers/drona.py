import requests
from config import DRONA_URL, DRONA_PASSWORD

class DronaProvider:
    def ask(self, prompt: str) -> str:
        if not DRONA_URL:
            raise Exception("DRONA_URL not set")

        r = requests.post(
            f"{DRONA_URL}/search",
            headers={
                "X-API-Key": DRONA_PASSWORD,
                "Content-Type": "application/json"
            },
            json={"query": prompt, "max_results": 5},
            timeout=15
        )
        r.raise_for_status()
        results = r.json().get("results", [])

        if not results:
            raise Exception("DRONA returned no results")

        formatted = []
        for i, result in enumerate(results[:5], 1):
            title   = result.get("title", "")
            snippet = result.get("content", result.get("snippet", ""))
            url     = result.get("url", "")
            formatted.append(f"{i}. {title}\n{snippet}\n{url}")

        return "\n\n".join(formatted)
