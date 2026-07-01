"""
services/auto_learn.py — Automatic Learning service.
Daily: review chats → extract lessons → store permanently → improve prompts → optimize memory.
Wires into APScheduler for automatic daily runs.
"""
from __future__ import annotations
import json, logging, os, sqlite3, time
from contextlib import contextmanager
from pathlib import Path

log = logging.getLogger("services.auto_learn")

_DB = str(Path(os.path.abspath(__file__)).parent.parent / "aiaurum.db")


@contextmanager
def _conn():
    con = sqlite3.connect(_DB)
    con.row_factory = sqlite3.Row
    con.execute("""CREATE TABLE IF NOT EXISTS learned_lessons (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        lesson TEXT NOT NULL,
        source TEXT DEFAULT \'chat\',
        category TEXT DEFAULT \'general\',
        importance INTEGER DEFAULT 3,
        created_at INTEGER DEFAULT (strftime('%s','now'))
    )""")
    con.execute("CREATE TABLE IF NOT EXISTS auto_learn_runs (id INTEGER PRIMARY KEY, username TEXT, run_at INTEGER, lessons_extracted INTEGER)")
    con.commit()
    try:
        yield con
        con.commit()
    finally:
        con.close()


def _ai(prompt: str, max_tokens: int = 800) -> str:
    token = os.getenv("GITHUB_TOKEN","")
    if not token: return "[]"
    try:
        import requests
        r = requests.post(
            "https://models.inference.ai.azure.com/chat/completions",
            headers={"Authorization":f"Bearer {token}","Content-Type":"application/json"},
            json={
                "model":"gpt-4o-mini",
                "messages":[
                    {"role":"system","content":"You extract learning insights from conversations. Output JSON only."},
                    {"role":"user","content":prompt},
                ],
                "max_tokens":max_tokens,"temperature":0.2,
            },
            timeout=30,
        )
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        log.error("_ai error: %s", e)
    return "[]"


def _get_todays_chats(username: str) -> list[str]:
    """Retrieve today's chat messages from the DB."""
    try:
        today_start = int(time.time()) - 86400
        con = sqlite3.connect(_DB)
        rows = con.execute(
            "SELECT messages FROM chats WHERE username=? AND updated_at > ?",
            (username, today_start)
        ).fetchall()
        con.close()
        conversations = []
        for row in rows:
            try:
                msgs = json.loads(row[0]) if isinstance(row[0], str) else row[0]
                if isinstance(msgs, list):
                    conversations.append("\n".join(
                        f"{m.get('role','?')}: {m.get('text', m.get('content',''))[:300]}"
                        for m in msgs[:10]
                    ))
            except Exception:
                pass
        return conversations
    except Exception as e:
        log.error("_get_todays_chats: %s", e)
        return []


def extract_lessons(username: str) -> list[dict]:
    """Extract lessons from today's conversations."""
    conversations = _get_todays_chats(username)
    if not conversations:
        return []

    combined = "\n\n---\n\n".join(conversations[:10])
    raw = _ai(
        f"""Analyse these AI conversations and extract valuable lessons.
Return JSON array: [{{"lesson": "...", "category": "fact|preference|technique|error|improvement", "importance": 1-5}}]
Maximum 10 lessons. Focus on: recurring topics, user preferences, mistakes made, good techniques used.

Conversations:
{combined[:4000]}""",
        max_tokens=600,
    )
    try:
        clean = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        lessons = json.loads(clean)
        return lessons if isinstance(lessons, list) else []
    except Exception:
        return []


def store_lessons(username: str, lessons: list[dict]) -> int:
    """Store extracted lessons in the DB. Returns count stored."""
    if not lessons:
        return 0
    with _conn() as con:
        for lesson in lessons:
            text = lesson.get("lesson","").strip()
            if not text:
                continue
            # Avoid duplicates
            exists = con.execute(
                "SELECT id FROM learned_lessons WHERE username=? AND lesson=?", (username, text)
            ).fetchone()
            if not exists:
                con.execute(
                    "INSERT INTO learned_lessons(username,lesson,category,importance) VALUES(?,?,?,?)",
                    (username, text, lesson.get("category","general"), lesson.get("importance",3)),
                )
    return len(lessons)


def get_lessons(username: str, category: str = "", limit: int = 20) -> list[dict]:
    """Retrieve stored lessons, optionally filtered by category."""
    with _conn() as con:
        if category:
            rows = con.execute(
                "SELECT * FROM learned_lessons WHERE username=? AND category=? ORDER BY importance DESC, created_at DESC LIMIT ?",
                (username, category, limit)
            ).fetchall()
        else:
            rows = con.execute(
                "SELECT * FROM learned_lessons WHERE username=? ORDER BY importance DESC, created_at DESC LIMIT ?",
                (username, limit)
            ).fetchall()
        return [dict(r) for r in rows]


def daily_learn_job(username: str) -> dict:
    """Full daily learning pipeline. Returns summary dict."""
    log.info("auto_learn: starting daily job for %s", username)
    lessons = extract_lessons(username)
    stored  = store_lessons(username, lessons)
    with _conn() as con:
        con.execute(
            "INSERT INTO auto_learn_runs(username,run_at,lessons_extracted) VALUES(?,?,?)",
            (username, int(time.time()), stored),
        )
    log.info("auto_learn: stored %d lessons for %s", stored, username)
    return {"lessons_extracted": stored, "lessons": lessons}


def get_lessons_as_context(username: str) -> str:
    """Return top lessons formatted as a system-prompt context string."""
    lessons = get_lessons(username, limit=5)
    if not lessons:
        return ""
    lines = [f"- [{l['category']}] {l['lesson']}" for l in lessons]
    return "\n\nLearned preferences & lessons:\n" + "\n".join(lines)


def schedule_daily(scheduler, username: str) -> None:
    """Register the daily learning job with APScheduler."""
    try:
        job_id = f"auto_learn_{username}"
        scheduler.add_job(
            daily_learn_job,
            trigger="cron", hour=3, minute=0,
            id=job_id, replace_existing=True,
            args=[username],
        )
        log.info("auto_learn: daily job scheduled for %s at 03:00", username)
    except Exception as e:
        log.warning("auto_learn: scheduler failed: %s", e)
