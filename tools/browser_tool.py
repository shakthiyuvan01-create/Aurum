"""
Browser automation tool — control a real browser using Playwright.
Actions: navigate, click, type, screenshot, scrape, fill_form, back, scroll.
"""
import os, base64, tempfile, logging

log = logging.getLogger(__name__)

NAME        = "browser_tool"
DESCRIPTION = (
    "Control a real web browser to automate tasks. "
    "Can navigate to URLs, click buttons, fill forms, take screenshots, and scrape page content. "
    "Use for: logging into websites, filling forms automatically, taking screenshots of pages, "
    "web scraping that requires JavaScript, or any browser automation task."
)
CATEGORY    = "builtin"
ICON        = "🌐"
INPUTS = [
    {"name": "action", "label": "Action", "type": "select",
     "options": [
         {"value": "navigate",   "label": "Navigate to URL"},
         {"value": "click",      "label": "Click element"},
         {"value": "type",       "label": "Type text"},
         {"value": "screenshot", "label": "Take screenshot"},
         {"value": "scrape",     "label": "Get page content"},
         {"value": "fill_form",  "label": "Fill a form"},
         {"value": "scroll",     "label": "Scroll page"},
         {"value": "back",       "label": "Go back"},
     ], "required": True},
    {"name": "url",      "label": "URL",          "type": "text",   "placeholder": "https://example.com"},
    {"name": "selector", "label": "CSS selector", "type": "text",   "placeholder": "#submit-btn  or  input[name=email]"},
    {"name": "text",     "label": "Text to type", "type": "text",   "placeholder": "Hello world"},
    {"name": "headless", "label": "Headless mode","type": "select",
     "options": [{"value":"true","label":"Yes (hidden)"},{"value":"false","label":"No (visible window)"}]},
]

_UPLOADS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads")


def _get_browser(headless: bool = True):
    """Launch or reuse a Playwright browser instance."""
    from playwright.sync_api import sync_playwright
    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=headless)
    return pw, browser


def run(action: str, url: str = "", selector: str = "", text: str = "",
        headless: str = "true") -> dict:
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    except ImportError:
        return {"error": "Playwright not installed. Run: pip install playwright && playwright install chromium"}

    is_headless = headless.lower() != "false"
    log.info("browser_tool: action=%s url=%s", action, url or '(none)')

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=is_headless)
            page    = browser.new_page()
            page.set_default_timeout(15000)

            # ── Navigate ──────────────────────────────────────────────────
            if action == "navigate":
                if not url:
                    return {"error": "url is required for navigate"}
                page.goto(url, wait_until="domcontentloaded")
                title = page.title()
                current = page.url
                return {"message": f"✅ Navigated to: {current}\nPage title: **{title}**"}

            # ── Screenshot ────────────────────────────────────────────────
            if action == "screenshot":
                if url:
                    page.goto(url, wait_until="domcontentloaded")
                fname  = f"screenshot_{os.urandom(4).hex()}.png"
                fpath  = os.path.join(_UPLOADS, fname)
                os.makedirs(_UPLOADS, exist_ok=True)
                page.screenshot(path=fpath, full_page=False)
                return {"message": f"✅ Screenshot saved!\n[📷 View screenshot](/uploads/{fname})",
                        "file": f"/uploads/{fname}"}

            # ── Scrape ────────────────────────────────────────────────────
            if action == "scrape":
                if url:
                    page.goto(url, wait_until="domcontentloaded")
                # Get visible text
                content = page.evaluate("""() => {
                    const els = document.querySelectorAll('p,h1,h2,h3,h4,li,td,th,span,div');
                    return Array.from(els)
                        .map(e => e.innerText?.trim())
                        .filter(t => t && t.length > 10)
                        .slice(0, 80)
                        .join('\\n');
                }""")
                if not content:
                    content = page.inner_text("body")
                return {"message": f"**Page content ({page.url}):**\n\n{content[:3000]}"}

            # ── Click ─────────────────────────────────────────────────────
            if action == "click":
                if url:
                    page.goto(url, wait_until="domcontentloaded")
                if not selector:
                    return {"error": "selector is required for click"}
                page.click(selector)
                page.wait_for_load_state("domcontentloaded")
                return {"message": f"✅ Clicked `{selector}` — now at: {page.url}"}

            # ── Type ──────────────────────────────────────────────────────
            if action == "type":
                if url:
                    page.goto(url, wait_until="domcontentloaded")
                if not selector:
                    return {"error": "selector is required for type"}
                if not text:
                    return {"error": "text is required for type"}
                page.fill(selector, text)
                return {"message": f"✅ Typed into `{selector}`: {text[:60]}"}

            # ── Fill form ─────────────────────────────────────────────────
            if action == "fill_form":
                if url:
                    page.goto(url, wait_until="domcontentloaded")
                # text should be JSON: {"#email": "user@example.com", "#pass": "secret"}
                try:
                    import json as _json
                    fields = _json.loads(text)
                    for sel, val in fields.items():
                        page.fill(sel, str(val))
                    return {"message": f"✅ Filled {len(fields)} form fields on {page.url}"}
                except Exception as e:
                    log.warning("fill_form JSON parse: %s", e)
                    return {"error": f"fill_form expects text as JSON: {{\"#selector\": \"value\"}} — {e}"}

            # ── Scroll ────────────────────────────────────────────────────
            if action == "scroll":
                if url:
                    page.goto(url, wait_until="domcontentloaded")
                page.evaluate("window.scrollBy(0, window.innerHeight)")
                return {"message": "✅ Scrolled down one page"}

            # ── Back ──────────────────────────────────────────────────────
            if action == "back":
                page.go_back()
                return {"message": f"✅ Went back — now at: {page.url}"}

            return {"error": f"Unknown action: {action}"}

    except Exception as e:
        log.error("browser_tool exception: action=%s error=%s", action, e)
        err = str(e)
        if "Executable doesn't exist" in err or "chromium" in err.lower():
            return {"error": "Chromium not installed. Run: playwright install chromium"}
        return {"error": f"Browser error: {err[:400]}"}
