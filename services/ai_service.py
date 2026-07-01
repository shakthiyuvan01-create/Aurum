"""
services/ai_service.py — Multi-signal capability router.
Maps messages to the best model using scoring across 6 capability dimensions.
"""
import os
import re
import logging

log = logging.getLogger("services.ai")

# ── Capability signal tables ───────────────────────────────────────────────────

_CODE_SIGNALS = {
    "tokens": {"python","javascript","typescript","java","c++","c#","golang","rust","sql",
               "bash","code","function","class","def","import","script","debug","error",
               "exception","traceback","loop","array","dict","list","regex","api","endpoint",
               "flask","django","react","html","css","json","xml","git","docker","kubernetes",
               "algorithm","leetcode","fix","bug","refactor","test","unittest","pytest"},
    "patterns": [r"```", r"def \w+", r"class \w+", r"import \w+", r"from \w+ import",
                 r"error:.*line \d+", r"traceback", r"\bsyntax\b"],
}

_RESEARCH_SIGNALS = {
    "tokens": {"explain","analyze","analyse","compare","essay","summarize","summarise",
               "research","difference","pros","cons","advantages","disadvantages","causes",
               "comprehensive","detailed","overview","history","background","impact","effect"},
    "patterns": [r"why does", r"how does", r"what causes", r"in depth", r"tell me about"],
}

_VISION_SIGNALS = {
    "tokens": {"image","photo","picture","screenshot","diagram","chart","graph","figure",
               "visual","see","look at","describe","ocr","text in","what's in","identify"},
    "patterns": [r"(attached|uploaded|this) (image|photo|pic|screenshot)"],
}

_REASONING_SIGNALS = {
    "tokens": {"prove","proof","logic","theorem","step by step","derive","formal","argument",
               "reasoning","inference","deduce","syllogism","hypothesis","paradox","ethics",
               "philosophy","implications"},
    "patterns": [r"step[- ]by[- ]step", r"prove that", r"is it true that"],
}

_QUICK_PATTERNS = [r"^(hi|hello|hey|thanks|ok|sure|yes|no|what time|whats|what's)\b"]

# ── Model capability map ───────────────────────────────────────────────────────
#
#  key     env var          default          best for
#  code  → CODE_MODEL     → gpt-4o          coding, debugging, refactoring
#  main  → MAIN_MODEL     → gpt-4o-mini     general, research, long analysis
#  fast  → FAST_MODEL     → gpt-4o-mini     quick Q&A, short chat
#  vision→ VISION_MODEL   → gemini-2.5-flash multimodal / image understanding
#  reason→ REASON_MODEL   → o1-mini         multi-step logic, proofs
#
# Override any via environment variable.

MODEL_COSTS: dict[str, float] = {
    # cost per 1K output tokens in USD (approximate)
    "gpt-4o":          0.015,
    "gpt-4o-mini":     0.0006,
    "o1-mini":         0.012,
    "gemini-2.5-flash":0.0012,
    "gemini-2.0-flash":0.0006,
    "llama3.2":        0.0,       # local — free
}


def _score(msg: str, signals: dict) -> int:
    low   = msg.lower()
    words = set(re.findall(r"\w+", low))
    score = len(words & signals.get("tokens", set()))
    for pat in signals.get("patterns", []):
        if re.search(pat, msg, re.I):
            score += 2
    return score


def route_model(msg: str, settings: dict) -> str:
    """
    Returns one of: 'code', 'main', 'fast', 'vision', 'reason'.
    Respects user's model_routing setting (0 = always use main).
    """
    if not settings.get("model_routing", 1):
        return "main"

    # If there's an image attached, always use vision model
    if settings.get("has_image"):
        return "vision"

    code     = _score(msg, _CODE_SIGNALS)
    research = _score(msg, _RESEARCH_SIGNALS)
    vision   = _score(msg, _VISION_SIGNALS)
    reasoning= _score(msg, _REASONING_SIGNALS)

    # Quick-chat fast path
    if any(re.match(p, msg.lower().strip()) for p in _QUICK_PATTERNS):
        return "fast"
    if len(msg) <= 60 and code == 0 and research == 0:
        return "fast"

    # Multi-step reasoning
    if reasoning >= 3 and reasoning > code and reasoning > research:
        return "reason"

    # Vision content
    if vision >= 2:
        return "vision"

    # Code work
    if code >= 2 and code >= research:
        return "code"

    # Deep research / long analysis
    if research >= 2 or len(msg) >= 300:
        return "main"

    return "fast"


def model_name(key: str, assistant_module=None) -> str:
    """Resolve routing key → actual model string from env or defaults."""
    default_main = getattr(assistant_module, "GITHUB_MODEL", "gpt-4o-mini") if assistant_module else "gpt-4o-mini"
    return {
        "code":   os.getenv("CODE_MODEL",   "gpt-4o"),
        "main":   os.getenv("MAIN_MODEL",   default_main),
        "fast":   os.getenv("FAST_MODEL",   "gpt-4o-mini"),
        "vision": os.getenv("VISION_MODEL", "gemini-2.5-flash"),
        "reason": os.getenv("REASON_MODEL", "o1-mini"),
    }.get(key, default_main)


def estimated_cost(key: str, output_tokens: int = 500) -> float:
    """Rough cost estimate for a response (USD)."""
    model = model_name(key)
    rate  = MODEL_COSTS.get(model, 0.001)
    return round(rate * output_tokens / 1000, 6)
