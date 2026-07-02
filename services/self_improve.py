"""
services/self_improve.py -- safeguarded self-improvement loop.

Weekly job (or manual POST /self_improve/run) that:
  1. Reviews recent failures: failed task history, error events, slow tools
  2. Asks the AI for concrete improvement suggestions
  3. Stores suggestions in a review table + memory -- NOTHING is auto-applied

Safeguards:
  - OFF by default (permission "self_improve" must be enabled explicitly)
  - Suggestions only: never edits code, configs, or permissions
  - Rate-limited to one run per 20 hours
  - Reviews are capped and human-readable via GET /self_improve/report
"""
import os
import sqlite3
import time
import logging

log = logging.getLogger("services.self_improve")

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "aiaurum.db")
MIN_INTERVAL_S = 20 * 3600


def _conn():
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("""CREATE TABLE IF NOT EXISTS self_improvements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        findings   TEXT DEFAULT '',
        suggestions TEXT DEFAULT '',
        created_at INTEGER DEFAULT (strftime('%s','now')))""")
    return con


def _gather_evidence(con) -> str:
    parts = []
    try:
        rows = con.execute(
            "SELECT title, detail, status, duration FROM task_history "
            "WHERE created_at > strftime('%s','now') - 7*86400 "
            "ORDER BY created_at DESC LIMIT 30").fetchall()
        if rows:
            failed = [r for r in rows if r["status"] != "done"]
            slow   = [r for r in rows if (r["duration"] or 0) > 60]
            parts.append("Tasks last 7 days: %d total, %d failed, %d slower than 60s"
                         % (len(rows), len(failed), len(slow)))
            for r in (failed + slow)[:10]:
                parts.append("- [%s, %.0fs] %s" % (r["status"], r["duration"] or 0, r["title"][:120]))
    except Exception as e:
        log.debug("history evidence: %s", e)
    try:
        rows = con.execute(
            "SELECT event, payload FROM agent_logs "
            "WHERE created_at > strftime('%s','now') - 7*86400 "
            "AND (payload LIKE '%error%' OR payload LIKE '%Error%') "
            "ORDER BY created_at DESC LIMIT 15").fetchall()
        if rows:
            parts.append("\nRecent error events:")
            for r in rows:
                parts.append("- %s: %s" % (r["event"], r["payload"][:150]))
    except Exception as e:
        log.debug("log evidence: %s", e)
    return "\n".join(parts) or "No failures or slow tasks recorded this week."


def run_review(force: bool = False) -> dict:
    from services.permission_manager import perms
    if not perms.check("self_improve"):
        return {"skipped": True,
                "reason": "self_improve permission is disabled (enable via POST /permissions)"}

    con = _conn()
    try:
        last = con.execute(
            "SELECT created_at FROM self_improvements ORDER BY id DESC LIMIT 1").fetchone()
        if last and not force and time.time() - last["created_at"] < MIN_INTERVAL_S:
            return {"skipped": True, "reason": "ran recently (rate limit: 20h)"}

        evidence = _gather_evidence(con)
        from providers import AI
        suggestions = AI.generate(
            "You are reviewing an AI assistant platform's weekly performance. "
            "Based on the evidence below, list at most 5 concrete, safe improvement "
            "suggestions (prompts to tune, tools to make async, retries to add). "
            "Do NOT suggest code you cannot see. Plain text, numbered.\n\nEVIDENCE:\n"
            + evidence,
            system="You produce cautious, actionable engineering suggestions only.",
            model="gpt-4o-mini", max_tokens=600, temperature=0.2)

        con.execute("INSERT INTO self_improvements (findings, suggestions) VALUES (?,?)",
                    (evidence[:4000], suggestions[:4000]))
        con.commit()
        try:
            import db
            db.add_memory("system", "Self-review %s: %s"
                          % (time.strftime("%Y-%m-%d"), suggestions[:400]))
        except Exception:
            pass
        try:
            from services.event_bus import bus
            bus.emit("self_improve.completed", {"username": "system"}, async_=True)
        except Exception:
            pass
        log.info("self-improvement review stored")
        return {"ok": True, "findings": evidence, "suggestions": suggestions}
    finally:
        con.close()


def get_reports(limit: int = 10) -> list:
    con = _conn()
    try:
        rows = con.execute(
            "SELECT * FROM self_improvements ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()
