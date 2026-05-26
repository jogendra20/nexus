import urllib.request as ur
import json
import urllib.parse
import threading

def _news(company: str, result_holder: list):
    try:
        q = urllib.parse.quote(f"{company} NSE BSE India")
        url = f"https://news.google.com/rss/search?q={q}&hl=en-IN&gl=IN&ceid=IN:en"
        req = ur.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        res = ur.urlopen(req, timeout=5)
        content = res.read().decode("utf-8")
        import re
        titles = re.findall(r"<title><!\[CDATA\[(.*?)\]\]></title>", content)
        result_holder.append(("news", titles[1:6]))
    except Exception as e:
        result_holder.append(("news", []))

def _nse(company: str, result_holder: list):
    try:
        q = urllib.parse.quote(company)
        url = f"https://www.nseindia.com/api/search/autocomplete?q={q}"
        req = ur.Request(url, headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json",
            "Referer": "https://www.nseindia.com"
        })
        res = ur.urlopen(req, timeout=5)
        data = json.loads(res.read())
        symbols = [s.get("symbol") for s in data.get("symbols", [])[:3] if s.get("symbol")]
        result_holder.append(("nse", symbols))
    except Exception as e:
        result_holder.append(("nse", []))

def run(query: str) -> dict:
    results = []

    t1 = threading.Thread(target=_news, args=(query, results))
    t2 = threading.Thread(target=_nse, args=(query, results))

    t1.start()
    t2.start()

    # Hard 6 second wall — both threads must finish or we move on
    t1.join(timeout=6)
    t2.join(timeout=6)

    news = []
    nse_symbols = []
    for key, val in results:
        if key == "news":
            news = val
        elif key == "nse":
            nse_symbols = val

    return {
        "company": query,
        "nse_symbols_found": nse_symbols,
        "recent_news": news,
        "arjun_note": (
            "Use nse_symbols_found to cross-reference announcements. "
            "Use recent_news for sentiment before entry decision."
        ),
        "source": "Google News RSS + NSE autocomplete (public)",
        "legal_note": "All data from public sources. No private financials accessed.",
    }
