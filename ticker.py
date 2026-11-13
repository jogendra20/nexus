"""
ticker.py - Live market data via Yahoo Finance
Works from Render, no auth needed.
"""
import urllib.request
import json

SYMBOLS = {
    "NIFTY 50": "^NSEI",
    "SENSEX":   "^BSESN",
    "BANKNIFTY":"^NSEBANK",
    "USDINR":   "INR=X",
}

def fetch_quote(symbol: str) -> dict | None:
    # Try query2 first, fall back to query1
    for base in ["https://query2.finance.yahoo.com", "https://query1.finance.yahoo.com"]:
        url = f"{base}/v8/finance/chart/{symbol}?interval=1m&range=1d"
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://finance.yahoo.com",
            "Origin": "https://finance.yahoo.com",
        })
        try:
            res = urllib.request.urlopen(req, timeout=8)
            data = json.loads(res.read())
            meta = data["chart"]["result"][0]["meta"]
            price = meta.get("regularMarketPrice", 0)
            prev  = meta.get("chartPreviousClose", price)
            change_pct = ((price - prev) / prev * 100) if prev else 0
            return {
                "price": round(price, 2),
                "change_pct": round(change_pct, 2),
                "up": change_pct >= 0,
            }
        except Exception as e:
            print(f"[Ticker] {base} {symbol} failed: {e}")
            continue
    return None

def get_ticker() -> list:
    items = []
    for name, symbol in SYMBOLS.items():
        q = fetch_quote(symbol)
        if q:
            arrow = "▲" if q["up"] else "▼"
            sign  = "+" if q["up"] else ""
            items.append(f"{name}  {arrow} {sign}{q['change_pct']}%  {q['price']}")
        else:
            items.append(f"{name}  — ")
    return items
