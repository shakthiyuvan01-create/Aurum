"""
services/auto_missions.py -- cron-triggered autonomous missions.

"Research BESS news every morning at 7 and email me a digest" becomes a
stored mission: the CEO team runs it on schedule and delivers the result
by email/telegram (permission-gated) or just saves it to chats/canvas.
"""
import json
import os
import sqlite3
import logging

log = logging.getLogger("services.auto_missions")

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "aiaurum.db")


def _conn():
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("""CREATE TABLE IF NOT EXISTS auto_missions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username  TEXT NOT NULL,
        goal      TEXT NOT NULL,
        cron_hour INTEGER DEFAULT 7,
        cron_min  INTEGER DEFAULT 0,
        deliver   TEXT DEFAULT 'canvas',   -- canvas | email | telegram
        deliver_to TEXT DEFAULT '',
        enabled   INTEGER DEFAULT 1,
        last_run  INTEGER DEFAULT 0,
        last_result TEXT DEFAULT '',
        created_at INTEGER DEFAULT (strftime('%s','now')))""")
    return con


def create(username, goal, hour=7, minute=0, deliver="canvas", deliver_to=""):
    with _conn() as con:
        cur = con.execute(
            "INSERT INTO auto_missions (username, goal, cron_hour, cron_min, deliver, deliver_to) "
            "VALUES (?,?,?,?,?,?)", (username, goal, hour, minute, deliver, deliver_to))
        return cur.lastrowid


def list_missions(username):
    with _conn() as con:
        return [dict(r) for r in con.execute(
            "SELECT * FROM auto_missions WHERE username=? ORDER BY id DESC", (username,))]


def remove(username, mission_id):
    with _conn() as con:
        con.execute("DELETE FROM auto_missions WHERE id=? AND username=?",
                    (mission_id, username))


def _deliver(mission, report):
    kind = mission["deliver"]
    title = "Mission: " + mission["goal"][:60]
    try:
        if kind == "email" and mission["deliver_to"]:
            import tools as _tools
            r = _tools.call("email", to=mission["deliver_to"], subject=title,
                            body=report[:8000])
            return "email: " + str(r.get("message", r.get("error", "sent")))[:100]
        if kind == "telegram":
            import tools as _tools
            r = _tools.call("messaging", message=(title + "\n\n" + report)[:3800],
                            username=mission["username"])
            return "telegram: " + str(r.get("message", r.get("error", "sent")))[:100]
    except Exception as e:
        log.warning("mission delivery failed: %s", e)
    # default: save to canvas
    try:
        import time as _t
        with _conn() as con:
            con.execute("INSERT INTO canvas_docs (username, title, content) VALUES (?,?,?)",
                        (mission["username"], title + " " + _t.strftime("%Y-%m-%d"), report))
        return "saved to canvas"
    except Exception as e:
        return "delivery failed: %s" % e


def run_due():
    """Called every 15 min by APScheduler: run any mission whose time window
    is now and which has not run in the last 20 hours."""
    import time
    now = time.localtime()
    with _conn() as con:
        due = [dict(r) for r in con.execute(
            "SELECT * FROM auto_missions WHERE enabled=1 AND "
            "cron_hour=? AND abs(cron_min - ?) < 15 AND "
            "last_run < strftime('%s','now') - 72000",
            (now.tm_hour, now.tm_min)).fetchall()]
    for m in due:
        try:
            log.info("auto mission #%d: %s", m["id"], m["goal"][:60])
            import agents
            result = agents.run_team(m["goal"], username=m["username"])
            report = result.get("reply", "")
            status = _deliver(m, report)
            with _conn() as con:
                con.execute("UPDATE auto_missions SET last_run=strftime('%s','now'), "
                            "last_result=? WHERE id=?", (status, m["id"]))
            try:
                from services.activity_log import record_task
                record_task(m["username"], "auto_mission", m["goal"][:200],
                            detail=status, duration=result.get("duration", 0))
            except Exception:
                pass
        except Exception as e:
            log.error("auto mission #%d failed: %s", m["id"], e)
    return len(due)
