"""Web search skill — search the web and return results."""
from skills import Skill


def _execute(query: str, num_results: int = 5) -> dict:
    try:
        from assistant.web import fetch_web_search
        results = fetch_web_search(query, num_results)
        return {"success": True, "results": results, "query": query}
    except Exception as e:
        return {"success": False, "error": str(e), "query": query}


def register_skill(registry):
    registry.register(Skill(
        name="web_search",
        description="Search the web and return results",
        execute=_execute,
        category="research",
    ))
