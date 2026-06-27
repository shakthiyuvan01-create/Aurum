"""Web search tool — DuckDuckGo live search."""

NAME        = "web_search"
DESCRIPTION = "Search the web for current information, news, facts, or any topic"
CATEGORY    = "builtin"
ICON        = "🔍"
INPUTS = [
    {"name": "query",       "label": "Search Query", "type": "text",   "placeholder": "What to search for", "required": True},
    {"name": "max_results", "label": "Max Results",  "type": "number", "placeholder": "5"},
]


def run(query: str, max_results: int = 5) -> dict:
    try:
        from duckduckgo_search import DDGS
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=int(max_results)):
                results.append({
                    "title":   r.get("title", ""),
                    "url":     r.get("href", ""),
                    "snippet": r.get("body", ""),
                })
        if not results:
            return {"message": "No results found for that query."}

        lines = []
        for i, r in enumerate(results, 1):
            lines.append(f"**{i}. {r['title']}**\n{r['snippet']}\n🔗 {r['url']}")
        return {"message": "\n\n".join(lines), "results": results}
    except ImportError:
        return {"error": "duckduckgo-search not installed. Run: pip install duckduckgo-search"}
    except Exception as e:
        return {"error": f"Search failed: {e}"}
