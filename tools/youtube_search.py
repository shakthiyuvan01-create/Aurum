"""YouTube search tool — find videos via DuckDuckGo."""

NAME        = "youtube_search"
DESCRIPTION = "Search YouTube for videos on any topic and get video links"
CATEGORY    = "builtin"
ICON        = "▶️"
INPUTS = [
    {"name": "query",       "label": "Search Query", "type": "text",   "placeholder": "Search YouTube...", "required": True},
    {"name": "max_results", "label": "Max Results",  "type": "number", "placeholder": "5"},
]


def run(query: str, max_results=5) -> dict:
    try:
        max_results = max(1, min(int(str(max_results).strip() or 5), 10))
    except (ValueError, TypeError):
        max_results = 5
    try:
        from duckduckgo_search import DDGS
        results = []

        # Try video search first
        try:
            with DDGS() as ddgs:
                for r in ddgs.videos(query, max_results=int(max_results)):
                    url = r.get("content") or r.get("url", "")
                    if "youtube" in url or "youtu.be" in url:
                        results.append({
                            "title":       r.get("title", ""),
                            "url":         url,
                            "description": r.get("description", ""),
                            "duration":    r.get("duration", ""),
                            "uploader":    r.get("uploader", ""),
                        })
        except Exception:
            pass

        # Fallback: text search scoped to youtube.com
        if not results:
            with DDGS() as ddgs:
                for r in ddgs.text(f"site:youtube.com {query}", max_results=int(max_results)):
                    href = r.get("href", "")
                    if "youtube.com/watch" in href or "youtu.be" in href:
                        results.append({
                            "title":       r.get("title", ""),
                            "url":         href,
                            "description": r.get("body", ""),
                        })

        if not results:
            return {"message": f"No YouTube results found for: {query}"}

        lines = []
        for r in results[:int(max_results)]:
            dur = f" ({r['duration']})" if r.get("duration") else ""
            upl = f" — {r['uploader']}" if r.get("uploader") else ""
            desc = r.get("description", "")[:120]
            lines.append(f"▶️ **{r['title']}**{dur}{upl}\n{desc}\n🔗 {r['url']}")

        return {"message": "\n\n".join(lines), "results": results}

    except ImportError:
        return {"error": "duckduckgo-search not installed. Run: pip install duckduckgo-search"}
    except Exception as e:
        return {"error": f"YouTube search failed: {e}"}
