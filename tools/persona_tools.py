"""
tools/persona_tools.py — Persona self-modification tools for Aurum.
Auto-discovered by the tools registry. Maps to the persona tool declarations.
"""
from __future__ import annotations

from services.persona import (
    write as _write_persona,
    append_daily_log,
    bootstrap_complete,
)

NAME = "persona"
DESCRIPTION = "Self-modification: read/write persona files (SOUL, IDENTITY, USER, MEMORY, HEARTBEAT)"
CATEGORY = "builtin"
ICON = "🧠"

INPUTS = [
    {"name": "action", "label": "Action", "type": "str",
     "required": True, "placeholder": "memory_replace | soul_replace | persona_replace | daily_log_append | bootstrap_complete"},
    {"name": "file", "label": "Persona file (for persona_replace)", "type": "str",
     "placeholder": "identity | user | heartbeat"},
    {"name": "markdown", "label": "Markdown content", "type": "str", "placeholder": "Full markdown content for replace actions"},
    {"name": "line", "label": "Log line (for daily_log_append)", "type": "str", "placeholder": "One line for daily log"},
]


def run(action: str = "", file: str = "", markdown: str = "", line: str = "") -> dict:
    """Run a persona tool action."""
    action = action.strip().lower()
    if action == "memory_replace":
        return _write_persona("MEMORY.md", markdown)
    elif action == "soul_replace":
        return _write_persona("SOUL.md", markdown)
    elif action == "persona_replace":
        file = file.strip().lower()
        if file == "identity":
            return _write_persona("IDENTITY.md", markdown)
        elif file == "user":
            return _write_persona("USER.md", markdown)
        elif file == "heartbeat":
            return _write_persona("HEARTBEAT.md", markdown)
        else:
            return {"error": f"Unknown persona file: {file}"}
    elif action == "daily_log_append":
        return append_daily_log(line)
    elif action == "bootstrap_complete":
        return bootstrap_complete()
    else:
        return {"error": f"Unknown persona action: {action}"}
