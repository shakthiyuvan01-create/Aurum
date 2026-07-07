"""
services/heartbeat.py -- autonomous self-maintenance loop (Ada-SI style).

On a timer, Aurum wakes up (user sees nothing), reads its own recent activity
(chats + task history), compares it to its persistent MEMORY.md, and rewrites
memory to capture durable new facts. This is genuine, bounded self-improvement:
the assistant's memory of you gets sharper on its own.

Gated behind the 'heartbeat' permission (OFF by default). Interval configurable
via HEARTBEAT_MINUTES (default 60). Never touches SOUL/IDENTITY - only MEMORY.
"""
import os
import sqlite3
import time
import logging

log = logging.getLogger("services.heartbeat")

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "aiaurum.db")
_last_run = 0


def _recent_activity(limit_chats: int = 25) -> str:
    lines = []
    try:
        con = sqlite3.connect(DB_PATH, timeout=5)
        con.row_factory = sqlite3.Row
        for r in con.execute(
                "SELECT c.title, m.role, m.text FROM chats c "
                "JOIN messages m ON m.chat_id=c.id "
                "WHERE c.created_at > strftime('%s','now','-2 days') "
                "ORDER BY m.id DESC LIMIT ?", (limit_chats * 2,)):
            t = (r["text"] or "")[:200]
            if t:
                lines.append("[%s] %s" % (r["role"], t))
        for r in con.execute(
                "SELECT title, detail FROM task_history "
                "WHERE created_at > strftime('%s','now','-2 days') "
                "ORDER BY created_at DESC LIMIT 20"):
            lines.append("[task] %s %s" % (r["title"], r["detail"] or ""))
        con.close()
    except Exception as e:
        log.debug("activity read: %s", e)
    return "\n".join(reversed(lines))[:6000]


def run_tick(force: bool = False) -> dict:
    from services.permission_manager import perms
    if not perms.check("heartbeat"):
        return {"skipped": True, "reason": "heartbeat permission disabled"}

    from services import persona
    from providers import AI

    activity = _recent_activity()
    if len(activity) < 40 and not force:
        return {"skipped": True, "reason": "not enough recent activity"}

    hb_rules = persona.read("HEARTBEAT")
    current_memory = persona.read("MEMORY")

    result = AI.generate(
        "%s\n\n=== RECENT_ACTIVITY ===\n%s\n\n=== CURRENT_MEMORY ===\n%s\n\n"
        "Following your HEARTBEAT rules above, output the FULL updated MEMORY.md "
        "(keep the existing structure and headers). If nothing durable is new, "
        "reply with exactly: NO_CHANGE"
        % (hb_rules, activity, current_memory),
        model=os.getenv("FAST_MODEL", "gpt-4o-mini"),
        max_tokens=1200, temperature=0.2)

    if not result or result.startswith("[AI error"):
        return {"error": "generation failed"}
    result = result.strip()
    if result == "NO_CHANGE" or "NO_CHANGE" in result[:20]:
        log.info("heartbeat: memory already accurate")
        return {"ok": True, "updated": False}
    if not result.startswith("#"):
        # guard against non-markdown drift
        return {"ok": True, "updated": False, "note": "output not applied (not markdown)"}

    persona.write("MEMORY", result, by_ai=True)
    log.info("heartbeat: MEMORY.md updated (%d chars)", len(result))
    try:
        from services.event_bus import bus
        bus.emit("heartbeat.memory_updated", {"chars": len(result)}, async_=True)
    except Exception:
        pass
    return {"ok": True, "updated": True, "memory_chars": len(result)}


def supervisor():
    """Called by APScheduler; respects the configured interval."""
    global _last_run
    interval = int(os.getenv("HEARTBEAT_MINUTES", "60")) * 60
    if time.time() - _last_run < interval:
        return
    _last_run = time.time()
    run_tick()
