"""
services/heartbeat.py -- autonomous self-maintenance loop (Ada-SI pattern).

On a timer, Aurum wakes up (user sees nothing), reads its own recent activity
(chats + task history + daily logs), compares it to its persistent MEMORY.md,
and rewrites memory to capture durable new facts.

Gated behind the 'heartbeat' permission (OFF by default). Interval configurable
via persona_config.json or HEARTBEAT_MINUTES env var (default 30 min).
Only ever touches MEMORY - never SOUL/IDENTITY/USER/AGENTS/TOOLS.
"""
from __future__ import annotations

import logging
import os
import sqlite3
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict

log = logging.getLogger("services.heartbeat")

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "aiaurum.db")

_heartbeat_lock = threading.Lock()

MAINTENANCE_SYSTEM_PROMPT = (
    "You are the Aurum maintenance brain. Your job is to keep MEMORY.md accurate.\n\n"
    "Read RECENT_ACTIVITY and RECENT_DAILY_LOGS below, compare against "
    "CURRENT_MEMORY_MD, then:\n"
    "- If daily logs contain durable facts not yet in MEMORY.md, output the FULL "
    "updated MEMORY.md (keep existing structure and headers).\n"
    "- If MEMORY.md is already accurate, reply with exactly: NO_CHANGE\n\n"
    "Rules:\n"
    "- Only update MEMORY.md. Never suggest changes to SOUL, IDENTITY, USER, AGENTS, or TOOLS.\n"
    "- Names, preferences, deadlines, projects, decisions go in memory.\n"
    "- Venting, complaints, one-off moods do NOT belong.\n"
    "- Never invent facts. Only record what actually appears in the activity/logs.\n"
    "- Output valid markdown starting with # header if updating."
)


def _recent_activity(limit_chats: int = 25) -> str:
    """Read recent chats and task history as a formatted text block."""
    lines: list[str] = []
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


def _build_user_message(
    hb_rules: str,
    activity: str,
    daily_logs_tail: str,
    current_memory: str,
) -> str:
    """Build the heartbeat turn user message with full context."""
    parts = [
        "=== HEARTBEAT_MD ===",
        hb_rules,
    ]
    if activity:
        parts.extend(["", "=== RECENT_ACTIVITY ===", activity])
    if daily_logs_tail:
        parts.extend(["", "=== RECENT_DAILY_LOGS ===", daily_logs_tail])
    parts.extend(["", "=== CURRENT_MEMORY_MD ===", current_memory])
    return "\n".join(parts)


def run_tick(force: bool = False) -> Dict[str, Any]:
    """Run one heartbeat maintenance pass.

    Reads recent activity + daily logs, asks the AI to consolidate durable
    facts into MEMORY.md. Uses the provider chain's text generation.

    Args:
        force: Skip rate limiting and min-activity checks when True.

    Returns:
        {"ok": True, "updated": True/False} or {"error": ...}
    """
    from services.permission_manager import perms
    if not perms.check("heartbeat"):
        return {"skipped": True, "reason": "heartbeat permission disabled"}

    if not _heartbeat_lock.acquire(blocking=False):
        return {"skipped": True, "reason": "heartbeat already running"}

    try:
        from services import persona
        from providers import AI

        activity = _recent_activity()
        if len(activity) < 40 and not force:
            return {"skipped": True, "reason": "not enough recent activity"}

        hb_rules = persona.read_heartbeat_instructions()
        daily_logs = persona.tail_recent_daily_logs(days=7)
        current_memory = persona.read("MEMORY")

        user_msg = _build_user_message(hb_rules, activity, daily_logs, current_memory)

        result = AI.generate(
            user_msg,
            system=MAINTENANCE_SYSTEM_PROMPT,
            model=os.getenv("FAST_MODEL", "gpt-4o-mini"),
            max_tokens=1200,
            temperature=0.2,
        )

        if not result or result.startswith("[AI error"):
            return {"error": "generation failed"}
        result = result.strip()
        if result == "NO_CHANGE" or result[:20].strip() == "NO_CHANGE":
            log.info("heartbeat: memory already accurate")
            return {"ok": True, "updated": False}
        if not result.startswith("#"):
            log.info("heartbeat: output not applied (not markdown)")
            return {"ok": True, "updated": False, "note": "output not applied"}

        wr = persona.write("MEMORY.md", result, by_ai=True)
        if not wr.get("ok"):
            return {"error": f"write failed: {wr.get('error')}"}

        log.info("heartbeat: MEMORY.md updated (%d chars)", len(result))

        try:
            persona.set_heartbeat_state(
                last_run_utc=datetime.now(timezone.utc).isoformat(),
                last_memory_updated=True,
            )
        except Exception as e:
            log.debug("heartbeat state save: %s", e)

        try:
            from services.event_bus import bus
            bus.emit("heartbeat.memory_updated", {"chars": len(result)}, async_=True)
        except Exception:
            pass

        return {"ok": True, "updated": True, "memory_chars": len(result)}

    except Exception as e:
        log.error("heartbeat run_tick failed: %s", e)
        return {"error": str(e)}
    finally:
        _heartbeat_lock.release()


_last_run: float = 0.0


def supervisor():
    """Called by APScheduler; checks config and rate limit before running."""
    global _last_run
    from services import persona
    try:
        config = persona.load_persona_config()
    except Exception:
        config = {}
    if not config.get("heartbeat_enabled", True):
        return
    interval_min = max(1, int(config.get("heartbeat_interval_minutes", 30) or 30))
    now = time.time()
    if now - _last_run < interval_min * 60:
        return
    _last_run = now
    run_tick()


async def supervisor_async():
    """Async supervisor wrapper - calls run_tick in a thread executor."""
    import asyncio
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, supervisor)
