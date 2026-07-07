"""
services/persona.py -- editable persona/soul files (Ada-SI style).

SOUL/IDENTITY/MEMORY/HEARTBEAT markdown shape Aurum's behavior and are injected
into every chat's system prompt. Aurum can self-edit MEMORY.md during heartbeat
passes. SOUL/IDENTITY are user-owned (edited via UI/API, not by the AI).
"""
import os
import logging

log = logging.getLogger("services.persona")

DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "persona")
FILES = ("SOUL", "IDENTITY", "MEMORY", "HEARTBEAT")
# The AI may only self-edit MEMORY; the rest are the user's to change.
AI_EDITABLE = {"MEMORY"}


def _path(name: str) -> str:
    name = name.upper().strip()
    if name not in FILES:
        raise ValueError("unknown persona file")
    return os.path.join(DIR, name + ".md")


def read(name: str) -> str:
    try:
        return open(_path(name), encoding="utf-8").read()
    except (OSError, ValueError):
        return ""


def write(name: str, content: str, by_ai: bool = False) -> dict:
    name = name.upper().strip()
    if name not in FILES:
        return {"error": "unknown file"}
    if by_ai and name not in AI_EDITABLE:
        return {"error": "AI may only edit MEMORY"}
    try:
        os.makedirs(DIR, exist_ok=True)
        open(_path(name), "w", encoding="utf-8").write(content[:20000])
        log.info("persona %s updated%s", name, " (by AI)" if by_ai else "")
        return {"ok": True, "file": name}
    except (OSError, ValueError) as e:
        return {"error": str(e)}


def system_block() -> str:
    """The persona block prepended to every chat system prompt."""
    parts = []
    for f in ("SOUL", "IDENTITY", "MEMORY"):
        c = read(f).strip()
        if c:
            parts.append(c)
    if not parts:
        return ""
    return "\n\n=== WHO YOU ARE ===\n" + "\n\n".join(parts)
