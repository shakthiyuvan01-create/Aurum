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
    'code'  → GPT-4o (CODE_MODEL)
    'fast'  → GPT-4o-mini (FAST_MODEL)
    'main'  → configured MAIN_MODEL
    Respects user's model_routing setting (0 = always use main).
    """
    if not settings.get("model_routing", 1):
        return "main"

    low   = msg.lower()
    words = set(low.split())

    if words & _CODE_KEYWORDS or any(k in low for k in _CODE_KEYWORDS if " " in k):
        return "code"
    if len(msg) < 120 and not any(k in low for k in _COMPLEX_KEYWORDS):
        return "fast"
    return "main"


def model_name(key: str, assistant_module) -> str:
    """Resolve routing key to actual model string."""
    return {
        "code": os.getenv("CODE_MODEL", "gpt-4o"),
        "fast": os.getenv("FAST_MODEL", "gpt-4o-mini"),
        "main": os.getenv("MAIN_MODEL", assistant_module.GITHUB_MODEL),
    }[key]
