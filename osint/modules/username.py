import urllib.request as ur
import concurrent.futures

# Only public platforms — no auth walls, no private data
PLATFORMS = {
    "GitHub":    "https://github.com/{}",
    "Twitter":   "https://twitter.com/{}",
    "Instagram": "https://www.instagram.com/{}",
    "Reddit":    "https://www.reddit.com/user/{}",
    "LinkedIn":  "https://www.linkedin.com/in/{}",
    "HackerNews":"https://news.ycombinator.com/user?id={}",
    "ProductHunt":"https://www.producthunt.com/@{}",
    "Dev.to":    "https://dev.to/{}",
    "Medium":    "https://medium.com/@{}",
    "Kaggle":    "https://www.kaggle.com/{}",
}

def _check(platform: str, url: str) -> dict:
    try:
        req = ur.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0"},
            method="HEAD"
        )
        res = ur.urlopen(req, timeout=6)
        status = res.status
        # 200 = exists, anything else = not found
        return {
            "platform": platform,
            "url": url,
            "exists": status == 200,
            "status": status
        }
    except Exception as e:
        code = getattr(e, 'code', None)
        # 404 = does not exist, 403 = exists but private
        exists = code == 403  # forbidden = profile exists but private
        return {
            "platform": platform,
            "url": url,
            "exists": exists,
            "status": code or "error"
        }

def run(query: str) -> dict:
    """
    Legal: HTTP HEAD requests to public profile URLs only.
    No login bypass. No private data. 200/403/404 only.
    """
    urls = {p: url.format(query) for p, url in PLATFORMS.items()}
    results = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
        futures = {ex.submit(_check, p, u): p for p, u in urls.items()}
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())

    found = [r for r in results if r["exists"]]
    not_found = [r for r in results if not r["exists"]]

    return {
        "username": query,
        "found_on": found,
        "not_found_on": not_found,
        "total_checked": len(PLATFORMS),
        "total_found": len(found),
        "source": "Public HTTP profile URLs",
        "legal_note": (
            "Public profile existence only. "
            "No scraping of private data. "
            "No authentication bypass."
        ),
    }
