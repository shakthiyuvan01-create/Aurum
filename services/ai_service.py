"""
services/ai_service.py — model routing and AI call helpers
"""
import os, logging

log = logging.getLogger("services.ai")

# ── Keyword sets for model routing ───────────────────────────────────────────

_CODE_KEYWORDS = {
    "python","javascript","typescript","java","c++","c#","golang","rust","sql","bash",
    "code","function","class","method","def ","import ","script","debug","error","exception",
    "traceback","loop","array","dict","list","regex","api","endpoint","flask","django",
    "react","html","css","json","xml","git","docker","kubernetes","algorithm","leetcode",
}
_COMPLEX_KEYWORDS = {
    "explain","analyze","analyse","compare","essay","write a","summarize","summarise",
    "research","difference between","pros and cons","advantages","disadvantages",
    "how does","why does","what causes","in depth","detailed","comprehensive",
}


def route_model(msg: str, settings: dict) -> str:
    """
    Returns 'code', 'fast', or 'main'.
    'code'  → GPT-4o (CODE_MODEL)      — coding / debugging tasks
    'fast'  → GPT-4o-mini (FAST_MODEL) — short questions, chat, tool queries
    'main'  → configured MAIN_MODEL    — long analysis, essays, research
    Respects user's model_routing setting (0 = always use main).

    Speed strategy: default to 'fast' unless complexity signals demand more.
    gpt-4o-mini is ~2-3x faster and sufficient for most conversational turns.
    """
    if not settings.get("model_routing", 1):
        return "main"

    low   = msg.lower()
    words = set(low.split())

    # Code work → use code-optimised model
    if words & _CODE_KEYWORDS or any(k in low for k in _CODE_KEYWORDS if " " in k):
        return "code"

    # Genuinely complex requests -> main model
    if any(k in low for k in _COMPLEX_KEYWORDS):
        return "main"

    # Long messages (>= 300 chars) may need deeper reasoning -> main
    if len(msg) >= 300:
        return "main"

    # Everything else -> fast model (gpt-4o-mini is 2-3x faster)
    return "fast"


def model_name(key: str, assistant_module) -> str:
    # Resolve routing key to actual model string
    return {
        "code": os.getenv("CODE_MODEL", "gpt-4o"),
        "fast": os.getenv("FAST_MODEL", "gpt-4o-mini"),
        "main": os.getenv("MAIN_MODEL", assistant_module.GITHUB_MODEL),
    }[key]
