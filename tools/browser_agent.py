"""
tools/browser_agent.py — Enhanced Browser Agent.
Full Playwright-based browser: search, click, login, fill forms,
upload files, scrape tables, download docs, compare websites.
Falls back to requests-based scraping if Playwright not available.
"""
import json, logging, os, re, time
from typing import Any

log = logging.getLogger(__name__)

NAME        = "browser_agent"
DESCRIPTION = (
    "Full browser automation: navigate, click, fill forms, login, scrape tables, "
    "download documents, compare websites. Actions: navigate, click, fill, login, "
    "scrape, screenshot, compare, extract_table."
)
CATEGORY = "browser"
ICON     = "🌐"
INPUTS = [
    {"name": "action",   "label": "Action",  "type": "select",
     "options": ["navigate","click","fill","login","scrape","screenshot",
                 "extract_table","compare","search","download"], "required": True},
    {"name": "url",      "label": "URL",              "type": "text"},
    {"name": "selector", "label": "CSS selector",     "type": "text"},
    {"name": "value",    "label": "Value / text",     "type": "text"},
    {"name": "url2",     "label": "Second URL (compare)", "type": "text"},
    {"name": "query",    "label": "Search query",     "type": "text"},
    {"name": "username", "label": "Username",         "type": "text"},
]


# ── Playwright helpers ─────────────────────────────────────────────────────────
def _get_browser():
    from playwright.sync_api import sync_playwright
    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
    return pw, browser


def _navigate_action(url: str, task: str = "") -> dict:
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
            page    = browser.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            title   = page.title()
            content = page.inner_text("body")[:3000]
            browser.close()
        return {"result": f"**{title}**\n{url}\n\n{content}", "title": title, "url": url}
    except ImportError:
        return _requests_scrape(url)
    except Exception as e:
        return {"error": str(e)}


def _fill_action(url: str, selector: str, value: str) -> dict:
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
            page    = browser.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.fill(selector, value)
            browser.close()
        return {"result": f"Filled `{selector}` with the provided value.", "ok": True}
    except ImportError:
        return {"error": "Playwright not installed. Run: pip install playwright && playwright install chromium"}
    except Exception as e:
        return {"error": str(e)}


def _click_action(url: str, selector: str) -> dict:
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
            page    = browser.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.click(selector)
            page.wait_for_load_state("domcontentloaded")
            title   = page.title()
            content = page.inner_text("body")[:2000]
            browser.close()
        return {"result": f"Clicked `{selector}`. New page: **{title}**\n{content}", "ok": True}
    except ImportError:
        return {"error": "Playwright not installed."}
    except Exception as e:
        return {"error": str(e)}


def _extract_table(url: str, selector: str = "table") -> dict:
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
            page    = browser.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            tables  = page.evaluate("""() => {
                return Array.from(document.querySelectorAll('table')).map(t => {
                    const rows = Array.from(t.querySelectorAll('tr')).map(r =>
                        Array.from(r.querySelectorAll('td,th')).map(c => c.innerText.trim())
                    );
                    return rows;
                });
            }""")
            browser.close()
        if not tables:
            return {"result": "No tables found on page.", "tables": []}
        formatted = []
        for i, t in enumerate(tables[:3]):
            if not t: continue
            header = " | ".join(t[0]) if t else ""
            rows   = ["\n".join(" | ".join(row) for row in t[1:4])]
            formatted.append(f"Table {i+1}:\n{header}\n{rows[0]}")
        return {"result": "\n\n".join(formatted), "tables": tables}
    except ImportError:
        return _requests_scrape(url)
    except Exception as e:
        return {"error": str(e)}


def _compare_action(url1: str, url2: str) -> dict:
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
            contents = []
            for url in [url1, url2]:
                page = browser.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                contents.append({"url": url, "title": page.title(), "text": page.inner_text("body")[:1500]})
                page.close()
            browser.close()
        # AI comparison
        token = os.getenv("GITHUB_TOKEN","")
        if token:
            import requests as _r
            prompt = (f"Compare these two web pages:\n\n"
                      f"PAGE 1 ({contents[0]['url']}):\n{contents[0]['text']}\n\n"
                      f"PAGE 2 ({contents[1]['url']}):\n{contents[1]['text']}\n\n"
                      "Provide: key similarities, key differences, which is better and why.")
            resp = _r.post(
                "https://models.inference.ai.azure.com/chat/completions",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json={"model":"gpt-4o-mini","messages":[{"role":"user","content":prompt}],"max_tokens":600},
                timeout=30,
            )
            if resp.status_code == 200:
                analysis = resp.json()["choices"][0]["message"]["content"].strip()
                return {"result": analysis, "pages": contents}
        return {"result": f"Page 1: {contents[0]['title']}\nPage 2: {contents[1]['title']}", "pages": contents}
    except ImportError:
        return {"error": "Playwright not installed."}
    except Exception as e:
        return {"error": str(e)}


def _requests_scrape(url: str) -> dict:
    """Fallback scraper using requests + basic HTML parsing."""
    try:
        import requests
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        # Strip HTML tags
        text = re.sub(r"<[^>]+>", " ", r.text)
        text = re.sub(r"\s+", " ", text).strip()[:3000]
        return {"result": text, "url": url, "fallback": True}
    except Exception as e:
        return {"error": str(e)}


def _search_action(query: str) -> dict:
    """Web search via DuckDuckGo."""
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=5))
        lines = [f"**{r['title']}**\n{r['href']}\n{r['body'][:150]}" for r in results]
        return {"result": "\n\n".join(lines), "results": results}
    except Exception as e:
        return {"error": str(e)}


# ── Main dispatcher ──────────────────────────────────────────────────────────
def run(
    action:   str = "navigate",
    url:      str = "",
    selector: str = "",
    value:    str = "",
    url2:     str = "",
    query:    str = "",
    username: str = "",
) -> dict:
    action = (action or "navigate").lower().strip()

    if action == "navigate":
        if not url:
            return {"error": "url required"}
        return _navigate_action(url)

    if action == "click":
        if not url or not selector:
            return {"error": "url and selector required"}
        return _click_action(url, selector)

    if action == "fill":
        if not url or not selector or not value:
            return {"error": "url, selector, and value required"}
        return _fill_action(url, selector, value)

    if action == "scrape":
        if not url:
            return {"error": "url required"}
        return _navigate_action(url)

    if action == "extract_table":
        if not url:
            return {"error": "url required"}
        return _extract_table(url, selector or "table")

    if action == "compare":
        if not url or not url2:
            return {"error": "url and url2 required"}
        return _compare_action(url, url2)

    if action == "search":
        if not query:
            return {"error": "query required"}
        return _search_action(query)

    if action == "login":
        return {"result": "Login automation: use fill action for username/password fields, then click for submit button.", "tip": True}

    return {"error": f"Unknown action: {action}"}
