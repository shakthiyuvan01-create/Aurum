"""News tool — latest headlines via DuckDuckGo News."""
import logging

NAME        = "news"
DESCRIPTION = "Get the latest news headlines on any topic"
CATEGORY    = "builtin"
ICON        = "📰"
INPUTS = [
    {"name": "topic", "label": "Topic", "type": "text",
     "placeholder": "e.g. AI, cricket, Tesla, world news", "required": False, "default": ""},
    {"name": "count", "label": "Number of articles", "type": "select",
     "options": [{"value": "5", "label": "5"}, {"value": "10", "label": "10"},
                 {"value": "15", "label": "15"}],
     "required": False, "default": "5"},
]

log = logging.getLogger("tools.news")

def run(topic: str = "", count="5") -> dict:
    try:
        n = min(int(str(count).strip() or 5), 15)
    except (ValueError, TypeError):
        n = 5
    query = topic.strip() or "latest news today"
    try:
        from ddgs import DDGS
        with DDGS() as ddgs:
            raw = list(ddgs.news(query, max_results=n))
    except ImportError:
        return {"error": "ddgs package not installed. Run: pip install duckduckgo-search"}
    except Exception as e:
        log.error("News fetch failed: %s", e)
        return {"error": f"News fetch failed: {e}"}

    articles = [
        {
            "title":  r.get("title", ""),
            "body":   r.get("body", ""),
            "url":    r.get("url", ""),
            "source": r.get("source", ""),
            "date":   r.get("date", ""),
        }
        for r in raw
    ]
    return {"topic": query, "articles": articles, "count": len(articles)}
