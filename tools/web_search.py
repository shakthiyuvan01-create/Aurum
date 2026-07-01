"""
tools/web_search.py — Web search with Gemini grounded search (primary) + DuckDuckGo fallback.
Modes: search (default), news, research, price, compare, headlines
"""
import logging
import os

log = logging.getLogger(__name__)

NAME        = "web_search"
DESCRIPTION = (
    "Search the web for current information, news, facts, prices, or comparisons. "
    "Modes: search (default), news, research, price, compare (needs items list)"
)
CATEGORY = "builtin"
ICON     = "🔍"
INPUTS = [
    {"name": "query",   "label": "Search Query", "type": "text",   "placeholder": "What to search for", "required": False},
    {"name": "mode",    "label": "Mode",         "type": "select",
     "options": [
         {"value": "search",   "label": "General search"},
         {"value": "news",     "label": "Latest news"},
         {"value": "research", "label": "Deep research"},
         {"value": "price",    "label": "Price lookup"},
         {"value": "compare",  "label": "Compare items"},
         {"value": "headlines","label": "Top headlines"},
     ], "required": False, "default": "search"},
    {"name": "items",   "label": "Items to compare (comma-separated)", "type": "text",   "placeholder": "iPhone 16, Galaxy S25", "required": False},
    {"name": "aspect",  "label": "Comparison aspect",                  "type": "text",   "placeholder": "battery life, price", "required": False},
    {"name": "max_results", "label": "Max results (DDG fallback)", "type": "number", "placeholder": "6"},
]


# ── Gemini grounded search ────────────────────────────────────────────────────

def _gemini_key() -> str:
    key = os.getenv("GEMINI_API_KEY", "")
    if not key:
        raise EnvironmentError("GEMINI_API_KEY not set")
    return key


def _gemini_search(query: str) -> str:
    from google import genai
    client   = genai.Client(api_key=_gemini_key())
    response = client.models.generate_content(
        model   = "gemini-2.5-flash",
        contents= query,
        config  = {"tools": [{"google_search": {}}]},
    )
    text = ""
    for part in response.candidates[0].content.parts:
        if hasattr(part, "text") and part.text:
            text += part.text
    text = text.strip()
    if not text:
        raise ValueError("Gemini returned empty response")
    return text


def _ddg_search(query: str, max_results: int = 6) -> list:
    try:
        from ddgs import DDGS
    except ImportError:
        from duckduckgo_search import DDGS
    results = []
    with DDGS() as ddgs:
        for r in ddgs.text(query, max_results=max_results):
            results.append({
                "title":   r.get("title",  ""),
                "snippet": r.get("body",   ""),
                "url":     r.get("href",   ""),
            })
    return results


def _format_ddg(query: str, results: list) -> str:
    if not results:
        return f"No results found for: {query}"
    lines = [f"Search results for: {query}\n"]
    for i, r in enumerate(results, 1):
        if r.get("title"):   lines.append(f"{i}. {r['title']}")
        if r.get("snippet"): lines.append(f"   {r['snippet']}")
        if r.get("url"):     lines.append(f"   {r['url']}")
        lines.append("")
    return "\n".join(lines).strip()


# ── Mode handlers ─────────────────────────────────────────────────────────────

def _search(query: str, max_results: int) -> str:
    try:
        return _gemini_search(query)
    except Exception as e:
        log.warning("Gemini search failed (%s), DDG fallback", e)
        return _format_ddg(query, _ddg_search(query, max_results))


def _news(query: str, max_results: int) -> str:
    nq = f"latest news today: {query}" if query else "top world news today"
    try:
        return _gemini_search(nq)
    except Exception as e:
        log.warning("Gemini news failed (%s), DDG fallback", e)
        return _format_ddg(nq, _ddg_search(nq, max_results + 2))


def _research(query: str, max_results: int) -> str:
    rq = (
        f"Comprehensive, detailed explanation of: {query}. "
        "Include background context, key facts, current state, and important nuances."
    )
    try:
        return _gemini_search(rq)
    except Exception as e:
        log.warning("Gemini research failed (%s), DDG fallback", e)
        return _format_ddg(query, _ddg_search(query, max_results + 4))


def _price(query: str, max_results: int) -> str:
    pq = f"current price of {query} — how much does it cost today"
    try:
        return _gemini_search(pq)
    except Exception as e:
        log.warning("Gemini price failed (%s), DDG fallback", e)
        return _format_ddg(pq, _ddg_search(f"{query} price buy", max_results))


def _compare(items: list, aspect: str) -> str:
    aspect = aspect or "general features"
    q = f"Compare {', '.join(items)} in terms of {aspect}. Give specific facts and data."
    try:
        return _gemini_search(q)
    except Exception as e:
        log.warning("Gemini compare failed (%s), DDG fallback", e)
        lines = [f"Comparison — {aspect.upper()}", "─" * 40]
        for item in items:
            lines.append(f"\n▸ {item}")
            for r in _ddg_search(f"{item} {aspect}", 3)[:2]:
                if r.get("snippet"): lines.append(f"  • {r['snippet']}")
                if r.get("url"):     lines.append(f"    {r['url']}")
        return "\n".join(lines)


def _headlines(n: int = 5) -> str:
    import re
    try:
        from google import genai
        client   = genai.Client(api_key=_gemini_key())
        response = client.models.generate_content(
            model   = "gemini-2.5-flash",
            contents= f"Current world news: {n} headlines. Numbered list, titles only.",
            config  = {"tools": [{"google_search": {}}]},
        )
        raw = "".join(
            p.text for p in response.candidates[0].content.parts
            if hasattr(p, "text") and p.text
        ).strip()
        result = []
        for line in raw.split("\n"):
            line = line.strip()
            if not line or not re.match(r"^\d+[.\)\-]", line):
                continue
            clean = re.sub(r"^\d+[.\)\-]\s*", "", line)
            clean = re.sub(r"^\*+\s*", "", clean).strip()
            if clean and len(clean) > 10:
                result.append(clean)
        if result:
            return "Top headlines:\n" + "\n".join(f"{i+1}. {h}" for i, h in enumerate(result[:n]))
        return raw
    except Exception as e:
        log.warning("Gemini headlines failed (%s), DDG fallback", e)
        results = _ddg_search("world news today", n)
        return "Top headlines:\n" + "\n".join(f"{i+1}. {r['title']}" for i, r in enumerate(results) if r.get("title"))


# ── Public entry point (Flask tool plugin interface) ──────────────────────────

def run(
    query:       str  = "",
    mode:        str  = "search",
    items:       str  = "",
    aspect:      str  = "",
    max_results: int  = 6,
    username:    str  = "",
) -> dict:
    query  = (query  or "").strip()
    mode   = (mode   or "search").lower().strip()
    aspect = (aspect or "").strip()
    try:
        max_results = max(1, min(int(str(max_results).strip() or 6), 20))
    except (ValueError, TypeError):
        max_results = 6

    # items can come as comma-separated string or list
    if isinstance(items, str):
        item_list = [x.strip() for x in items.split(",") if x.strip()]
    else:
        item_list = list(items) if items else []

    # auto-detect compare mode
    if item_list and mode not in ("compare",):
        mode = "compare"

    if mode == "headlines":
        return {"result": _headlines(max_results)}

    if not query and not item_list:
        return {"error": "Please provide a search query."}

    log.info("web_search mode=%s query=%r", mode, query or item_list)

    try:
        if mode == "compare" and item_list:
            result = _compare(item_list, aspect)
        elif mode == "news":
            result = _news(query, max_results)
        elif mode == "research":
            result = _research(query, max_results)
        elif mode == "price":
            result = _price(query, max_results)
        else:
            result = _search(query, max_results)
        return {"result": result}
    except Exception as e:
        log.error("web_search failed: %s", e)
        return {"error": str(e)}
