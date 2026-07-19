"""
services/gamification.py -- XP, levels, and rank titles (Ada-SI gamification).

Tracks user engagement via XP points earned through various actions.
Levels range 1-50 with increasing XP requirements per level.
Rank titles unlock at certain levels.
"""
from __future__ import annotations

import json
import logging
import math
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

log = logging.getLogger("services.gamification")

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "aiaurum.db")

# XP awards for different actions
XP_EVENTS = {
    "chat_message": 10,
    "tool_used": 25,
    "tool_forged": 100,
    "daily_login": 50,
    "workflow_completed": 75,
    "research_done": 60,
    "code_generated": 30,
    "image_generated": 40,
    "voice_message": 15,
    "memory_updated": 20,
    "heartbeat_run": 5,
    "bootstrap_complete": 200,
    "feedback_given": 30,
}

# Rank titles at milestone levels
RANKS = {
    1: "Novice",
    5: "Apprentice",
    10: "Operator",
    15: "Artisan",
    20: "Explorer",
    25: "Architect",
    30: "Scholar",
    35: "Virtuoso",
    40: "Sage",
    45: " Luminary",
    50: "Aurum Master",
}

# Base XP for level 2; each level requires more
BASE_XP = 100
XP_SCALE = 1.5


def xp_for_level(level: int) -> int:
    """XP required to reach a given level (1-indexed)."""
    if level <= 1:
        return 0
    return int(BASE_XP * (XP_SCALE ** (level - 2)))


def total_xp_for_level(level: int) -> int:
    """Cumulative XP needed to reach this level from level 1."""
    return sum(xp_for_level(i) for i in range(2, level + 1))


def level_from_xp(total_xp: int) -> int:
    """Calculate level from total XP (max 50)."""
    for lvl in range(2, 51):
        if total_xp < total_xp_for_level(lvl):
            return lvl - 1
    return 50


def rank_for_level(level: int) -> str:
    """Get rank title for a level."""
    best = "Novice"
    for lvl, title in sorted(RANKS.items()):
        if level >= lvl:
            best = title
    return best


def xp_progress(total_xp: int) -> Dict[str, Any]:
    """Get full XP/level/progress info."""
    level = level_from_xp(total_xp)
    current_level_xp = total_xp_for_level(level) if level > 1 else 0
    next_level_xp = total_xp_for_level(level + 1) if level < 50 else current_level_xp
    xp_in_level = total_xp - current_level_xp
    xp_needed = next_level_xp - current_level_xp

    return {
        "xp": total_xp,
        "level": level,
        "rank": rank_for_level(level),
        "xp_in_level": xp_in_level,
        "xp_needed_for_next": xp_needed,
        "progress_pct": round((xp_in_level / max(xp_needed, 1)) * 100, 1),
        "next_rank": rank_for_level(level + 1) if level < 50 else None,
    }


def _ensure_table():
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.execute("""CREATE TABLE IF NOT EXISTS gamification (
        username TEXT PRIMARY KEY,
        xp INTEGER DEFAULT 0,
        level INTEGER DEFAULT 1,
        data TEXT DEFAULT '{}',
        created_at INTEGER DEFAULT (strftime('%s','now')),
        updated_at INTEGER DEFAULT (strftime('%s','now'))
    )""")
    con.execute("""CREATE TABLE IF NOT EXISTS gamification_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        event TEXT,
        xp_gained INTEGER,
        total_xp INTEGER,
        level INTEGER,
        created_at INTEGER DEFAULT (strftime('%s','now'))
    )""")
    con.commit()
    con.close()


def _get_row(username: str) -> Optional[Dict[str, Any]]:
    _ensure_table()
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    try:
        row = con.execute(
            "SELECT * FROM gamification WHERE username = ?", (username,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        con.close()


def get_stats(username: str) -> Dict[str, Any]:
    """Get gamification stats for a user."""
    row = _get_row(username)
    if not row:
        return xp_progress(0)

    total_xp = row["xp"]
    stats = xp_progress(total_xp)
    stats["data"] = json.loads(row.get("data", "{}"))
    stats["updated_at"] = row.get("updated_at")
    return stats


def award_xp(username: str, event: str, multiplier: float = 1.0) -> Dict[str, Any]:
    """Award XP for an event. Returns updated stats.

    Args:
        username: User to award XP to
        event: Event type key (must be in XP_EVENTS)
        multiplier: Optional multiplier (e.g. 2.0 for double XP)

    Returns:
        Dict with XP gained, new total, new level, and whether they leveled up.
    """
    base_xp = XP_EVENTS.get(event)
    if base_xp is None:
        log.debug("unknown XP event: %s", event)
        return get_stats(username)

    xp_gained = int(base_xp * multiplier)
    con = sqlite3.connect(DB_PATH, timeout=10)
    try:
        _ensure_table()
        row = con.execute(
            "SELECT xp, level, data FROM gamification WHERE username = ?", (username,)
        ).fetchone()

        old_xp = row[0] if row else 0
        old_level = row[1] if row else 1
        new_xp = old_xp + xp_gained
        new_level = level_from_xp(new_xp)
        leveled_up = new_level > old_level

        data = {}
        if row and len(row) > 2 and row[2]:
            try:
                data = json.loads(row[2])
            except (json.JSONDecodeError, TypeError):
                data = {}

        if row:
            con.execute(
                "UPDATE gamification SET xp=?, level=?, data=?, updated_at=strftime('%s','now') WHERE username=?",
                (new_xp, new_level, json.dumps(data), username),
            )
        else:
            con.execute(
                "INSERT INTO gamification (username, xp, level, data) VALUES (?,?,?,?)",
                (username, new_xp, new_level, json.dumps(data)),
            )

        con.execute(
            "INSERT INTO gamification_log (username, event, xp_gained, total_xp, level) VALUES (?,?,?,?,?)",
            (username, event, xp_gained, new_xp, new_level),
        )
        con.commit()

        stats = xp_progress(new_xp)
        stats["event"] = event
        stats["xp_gained"] = xp_gained
        stats["leveled_up"] = leveled_up
        stats["old_level"] = old_level
        stats["data"] = data

        if leveled_up:
            log.info("gamification: %s reached level %d (%s)!", username, new_level,
                     rank_for_level(new_level))

        return stats

    except Exception as e:
        log.error("gamification award_xp: %s", e)
        return get_stats(username)
    finally:
        con.close()


def get_leaderboard(limit: int = 20) -> List[Dict[str, Any]]:
    """Get top users by XP."""
    _ensure_table()
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            "SELECT username, xp, level FROM gamification ORDER BY xp DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [
            {
                "username": r["username"],
                "xp": r["xp"],
                "level": r["level"],
                "rank": rank_for_level(r["level"]),
            }
            for r in rows
        ]
    finally:
        con.close()


def get_recent_activity(username: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Get recent XP events for a user."""
    _ensure_table()
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            "SELECT * FROM gamification_log WHERE username = ? ORDER BY id DESC LIMIT ?",
            (username, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def reset_user(username: str) -> Dict[str, Any]:
    """Reset a user's gamification data."""
    _ensure_table()
    con = sqlite3.connect(DB_PATH, timeout=10)
    try:
        con.execute("DELETE FROM gamification WHERE username = ?", (username,))
        con.commit()
        return {"ok": True, "message": f"Reset {username}'s gamification data"}
    except Exception as e:
        return {"error": str(e)}
    finally:
        con.close()
