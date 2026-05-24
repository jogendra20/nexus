import os, urllib.request, json

JINA_API_KEY = os.getenv("JINA_API_KEY", "")

class JinaProvider:
    def fetch(self, url: str, target_selector: str = None, remove_selector: str = None) -> dict:
        headers = {
            "Authorization": f"Bearer {JINA_API_KEY}",
            "Accept": "application/json",
            "X-Return-Format": "markdown"
        }
        if target_selector:
            headers["X-Target-Selector"] = target_selector
        if remove_selector:
            headers["X-Remove-Selector"] = remove_selector

        req = urllib.request.Request(
            f"https://r.jina.ai/{url}",
            headers=headers
        )
        try:
            res = urllib.request.urlopen(req, timeout=30)
            data = json.loads(res.read())
            content = data.get("data", {}).get("content", "")
            title = data.get("data", {}).get("title", "")
            return {"content": content, "title": title, "url": url, "success": True}
        except Exception as e:
            return {"content": "", "title": "", "url": url, "success": False, "error": str(e)}

    def ask(self, prompt: str, task: str = None) -> dict:
        # Extract URL from prompt
        import re
        urls = re.findall(r"https?://[^\s]+", prompt)
        if not urls:
            return {"response": "No URL found in prompt", "provider": "jina"}

        url = urls[0]
        result = self.fetch(url)
        if not result["success"]:
            return {"response": f"Jina fetch failed: {result.get('error')}", "provider": "jina"}

        return {
            "response": result["content"],
            "title": result["title"],
            "provider": "jina",
            "task": "scraping"
        }
