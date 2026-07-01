"""
plugins/stock_price.py — Example plugin: live stock price lookup.
DROP THIS FILE into plugins/ — it auto-loads with no code changes.
"""
import os

NAME        = "stock_price"
DESCRIPTION = "Get real-time stock price, change, and market cap for any ticker symbol."
CATEGORY    = "finance"
ICON        = "📈"
VERSION     = "1.0"
INPUTS = [
    {"name": "ticker",   "label": "Stock ticker (e.g. AAPL, TSLA)", "type": "text",   "required": True},
    {"name": "currency", "label": "Currency",                        "type": "select",
     "options": ["USD","EUR","GBP","INR"], "default": "USD"},
]


def run(ticker: str = "", currency: str = "USD", username: str = "") -> dict:
    if not ticker:
        return {"error": "ticker required"}
    ticker = ticker.upper().strip()
    try:
        import requests
        # Yahoo Finance unofficial endpoint
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=1d"
        r   = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        if r.status_code != 200:
            return {"error": f"Yahoo Finance returned {r.status_code}"}
        meta  = r.json()["chart"]["result"][0]["meta"]
        price = meta.get("regularMarketPrice", 0)
        prev  = meta.get("chartPreviousClose", price)
        chg   = round(price - prev, 4)
        pct   = round((chg / prev * 100) if prev else 0, 2)
        return {
            "result": (
                f"**{ticker}** — ${price:,.4f} {currency}\n"
                f"Change: {chg:+.4f} ({pct:+.2f}%)\n"
                f"Exchange: {meta.get('exchangeName','?')} | "
                f"Market state: {meta.get('marketState','?')} | "
                f"Currency: {meta.get('currency',currency)}"
            ),
            "ticker": ticker,
            "price": price,
            "change": chg,
            "change_pct": pct,
            "currency": meta.get("currency", currency),
        }
    except Exception as e:
        return {"error": str(e)}
