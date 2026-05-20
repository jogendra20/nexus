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
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1m&range=1d"
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
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
        print(f"[Ticker] {symbol} failed: {e}")
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
