"""services/user_learning.py - User habit learning, preference adaptation, knowledge updates"""
from __future__ import annotations
import json, logging, os, sqlite3, time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger("services.user_learning")
BASE = Path(__file__).resolve().parent.parent
DB_PATH = BASE / "aiaurum.db"

def _ensure():
    con = sqlite3.connect(str(DB_PATH), timeout=10)
    con.execute("""CREATE TABLE IF NOT EXISTS user_habits(
        id INTEGER PRIMARY KEY AUTOINCREMENT,username TEXT,pattern TEXT,category TEXT,
        frequency INTEGER DEFAULT 1,last_observed TEXT,confidence REAL DEFAULT 0.5,
        created_at INTEGER DEFAULT(strftime('%s','now')))""")
    con.execute("""CREATE TABLE IF NOT EXISTS user_preferences(
        id INTEGER PRIMARY KEY AUTOINCREMENT,username TEXT,pref_key TEXT UNIQUE,
        pref_value TEXT,category TEXT DEFAULT 'general',
        updated_at INTEGER DEFAULT(strftime('%s','now')))""")
    con.execute("""CREATE INDEX IF NOT EXISTS idx_habits_user ON user_habits(username)""")
    con.execute("""CREATE INDEX IF NOT EXISTS idx_prefs_user ON user_preferences(username)""")
    con.commit(); con.close()

def observe_habit(username: str, pattern: str, category: str = "general") -> Dict[str, Any]:
    """Record a user behavior pattern and update its frequency/confidence."""
    _ensure()
    con = sqlite3.connect(str(DB_PATH), timeout=10)
    existing = con.execute(
        "SELECT id,frequency FROM user_habits WHERE username=? AND pattern=?",
        (username, pattern)).fetchone()
    now = datetime.now(timezone.utc).isoformat()
    if existing:
        freq = existing[1] + 1
        confidence = min(0.95, 0.3 + (freq * 0.05))
        con.execute("UPDATE user_habits SET frequency=?,last_observed=?,confidence=? WHERE id=?",
                    (freq, now, confidence, existing[0]))
    else:
        con.execute("INSERT INTO user_habits(username,pattern,category,last_observed,confidence) VALUES(?,?,?,?,?)",
                    (username, pattern, category, now, 0.3))
    con.commit(); con.close()
    return {"pattern": pattern, "recorded": True}

def get_habits(username: str, min_confidence: float = 0.3) -> Dict[str, Any]:
    """Get learned user habits above a confidence threshold."""
    _ensure()
    con = sqlite3.connect(str(DB_PATH), timeout=10)
    rows = con.execute(
        "SELECT pattern,category,frequency,confidence,last_observed FROM user_habits "
        "WHERE username=? AND confidence>=? ORDER BY frequency DESC LIMIT 50",
        (username, min_confidence)).fetchall()
    con.close()
    habits = [{"pattern": r[0], "category": r[1], "frequency": r[2],
               "confidence": r[3], "last_observed": r[4]} for r in rows]
    return {"habits": habits, "count": len(habits)}

def set_preference(username: str, key: str, value: str, category: str = "general") -> Dict[str, Any]:
    """Store a user preference. Can be communication style, topics, etc."""
    _ensure()
    con = sqlite3.connect(str(DB_PATH), timeout=10)
    con.execute(
        "INSERT OR REPLACE INTO user_preferences(username,pref_key,pref_value,category,updated_at) VALUES(?,?,?,?,strftime('%s','now'))",
        (username, key, value, category))
    con.commit(); con.close()
    # Also store in persona system
    try:
        from services.persona import write as _pw
        _pw("USER.md", read("USER.md") + f"\n- {key}: {value}\n", by_ai=False)
    except: pass
    return {"key": key, "value": value, "stored": True}

def get_preferences(username: str, category: str = "") -> Dict[str, Any]:
    """Get stored user preferences, optionally filtered by category."""
    _ensure()
    con = sqlite3.connect(str(DB_PATH), timeout=10)
    if category:
        rows = con.execute(
            "SELECT pref_key,pref_value,category,updated_at FROM user_preferences WHERE username=? AND category=?",
            (username, category)).fetchall()
    else:
        rows = con.execute(
            "SELECT pref_key,pref_value,category,updated_at FROM user_preferences WHERE username=?",
            (username,)).fetchall()
    con.close()
    return {"preferences": {r[0]: r[1] for r in rows}, "count": len(rows)}

def update_knowledge(username: str, topic: str, facts: str) -> Dict[str, Any]:
    """Update Aurum's knowledge about a specific topic."""
    try:
        from services.learning import add_fact
        add_fact(f"{topic}: {facts}", username)
        from services.persona import append_daily_log
        append_daily_log(f"Knowledge updated: {topic}")
        return {"topic": topic, "updated": True}
    except Exception as e:
        return {"error": str(e)}

def get_learning_summary(username: str) -> Dict[str, Any]:
    """Get a comprehensive summary of what Aurum has learned about the user."""
    habits = get_habits(username)
    prefs = get_preferences(username)
    try:
        from services.learning import stats
        stats_data = stats() or {}
    except: stats_data = {}
    return {
        "username": username,
        "habits": habits,
        "preferences": prefs,
        "learning_stats": stats_data,
        "habit_count": habits.get("count", 0),
        "preference_count": prefs.get("count", 0),
    }

def suggest_automation(username: str) -> Dict[str, Any]:
    """Suggest automations based on learned patterns."""
    habits = get_habits(username, min_confidence=0.5)
    if not habits.get("habits"):
        return {"suggestions": [], "note": "Not enough data yet"}
    suggestions = []
    for h in habits["habits"]:
        if h["frequency"] >= 3:
            suggestions.append({
                "based_on": h["pattern"],
                "suggestion": f"Consider automating {h['pattern']}",
                "frequency": h["frequency"],
                "confidence": h["confidence"],
            })
    return {"suggestions": suggestions, "count": len(suggestions)}
