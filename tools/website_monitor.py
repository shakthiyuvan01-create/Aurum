"""
tools/website_monitor.py -- watch web pages for changes or keywords.

Actions:
  add    -- start watching a URL (optionally for a keyword)
  check  -- check one watch (or all due) right now
  list   -- show all watches + last status
  remove -- stop watching

State lives in SQLite (aiaurum.db). Pair with scheduler_tool to run
'check' periodically; alerts go through the messaging tool when configured.
"""
import hashlib
import os
import re
import sqlite3
import time
import logging

log = logging.getLogger("tools.website_monitor")

NAME        = "website_monitor"
DESCRIPTION = (
    "Monitor websites for content changes or keywords. "
    "Actions: add (url, keyword optional), check, list, remove (watch_id). "
    "Schedule periodic checks with scheduler_tool. Sends alerts via the "
    "messaging tool if MESSAGING_ALERTS=1."
)
CATEGORY = "builtin"
ICON     = "eye"
INPUTS = [
    {"name": "action", "label": "Action", "type": "select",
     "options": [{"value": "add", "label": "Add watch"},
                 {"value": "check", "label": "Check now"},
                 {"value": "list", "label": "List watches"},
                 {"value": "remove", "label": "Remove watch"}],
     "required": True},
    {"name": "url",      "label": "URL",              "type": "text"},
    {"name": "keyword",  "label": "Keyword (optional)", "type": "text"},
    {"name": "watch_id", "label": "Watch ID (check/remove)", "type": "text"},
    {"name": "username", "label": "Username", "type": "text"},
]

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "aiaurum.db")


def _conn():
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("""CREATE TABLE IF NOT EXISTS site_watches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username     TEXT NOT NULL,
        url          TEXT NOT NULL,
        keyword      TEXT DEFAULT '',
        last_hash    TEXT DEFAULT '',
        last_status  TEXT DEFAULT 'never checked',
        last_checked INTEGER DEFAULT 0,
        created_at   INTEGER DEFAULT (strftime('%s','now')))""")
    return con


def _fetch_text(url: str) -> str:
    import requests
    r = requests.get(url, timeout=20,
                     headers={"User-Agent": "Mozilla/5.0 (AI-Aurum monitor)"})
    r.raise_for_status()
    text = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", " ", r.text)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _alert(username: str, message: str):
    if os.getenv("MESSAGING_ALERTS", "0") != "1":
        return
    try:
        import tools as _tools
        _tools.call("messaging", message=message, username=username)
    except Exception as e:
        log.warning("alert failed: %s", e)


def _check_one(con, row) -> dict:
    from services.permission_manager import perms
    if not perms.check("network"):
        return perms.deny_message("network")
    try:
        text = _fetch_text(row["url"])
    except Exception as e:
        status = "fetch error: %s" % e
        con.execute("UPDATE site_watches SET last_status=?, last_checked=? WHERE id=?",
                    (status[:300], int(time.time()), row["id"]))
        return {"id": row["id"], "url": row["url"], "status": status}

    changed  = False
    keyword  = (row["keyword"] or "").strip()
    kw_found = bool(keyword) and keyword.lower() in text.lower()
    new_hash = hashlib.sha1(text.encode()).hexdigest()
    if row["last_hash"] and new_hash != row["last_hash"]:
        changed = True

    if keyword:
        status = "keyword FOUND" if kw_found else "keyword not found"
    else:
        status = "CHANGED" if changed else ("unchanged" if row["last_hash"] else "baseline saved")

    con.execute("UPDATE site_watches SET last_hash=?, last_status=?, last_checked=? WHERE id=?",
                (new_hash, status, int(time.time()), row["id"]))

    if changed or kw_found:
        _alert(row["username"], "Website alert: %s -> %s (%s)"
               % (row["url"], status, time.strftime("%Y-%m-%d %H:%M")))
        try:
            from services.event_bus import bus
            bus.emit("monitor.alert", {"username": row["username"], "url": row["url"],
                                       "status": status}, async_=True)
        except Exception:
            pass

    return {"id": row["id"], "url": row["url"], "status": status,
            "changed": changed, "keyword_found": kw_found if keyword else None}


def run(action: str = "list", url: str = "", keyword: str = "",
        watch_id: str = "", username: str = "default") -> dict:
    action = (action or "list").lower().strip()
    con = _conn()
    try:
        if action == "add":
            if not url.startswith(("http://", "https://")):
                return {"error": "valid http(s) url required"}
            cur = con.execute(
                "INSERT INTO site_watches (username, url, keyword) VALUES (?,?,?)",
                (username, url, keyword.strip()))
            con.commit()
            wid = cur.lastrowid
            row = con.execute("SELECT * FROM site_watches WHERE id=?", (wid,)).fetchone()
            first = _check_one(con, row)   # save baseline immediately
            con.commit()
            return {"ok": True, "watch_id": wid, "baseline": first,
                    "hint": "Schedule periodic checks: scheduler_tool add "
                            "'{\"tool\":\"website_monitor\",\"action\":\"check\"}' every hour"}

        if action == "check":
            if watch_id:
                rows = con.execute("SELECT * FROM site_watches WHERE id=? AND username=?",
                                   (watch_id, username)).fetchall()
            else:
                rows = con.execute("SELECT * FROM site_watches WHERE username=?",
                                   (username,)).fetchall()
            if not rows:
                return {"error": "no watches found"}
            results = [_check_one(con, r) for r in rows]
            con.commit()
            return {"ok": True, "results": results}

        if action == "remove":
            if not watch_id:
                return {"error": "watch_id required"}
            con.execute("DELETE FROM site_watches WHERE id=? AND username=?",
                        (watch_id, username))
            con.commit()
            return {"ok": True, "removed": watch_id}

        rows = con.execute(
            "SELECT id, url, keyword, last_status, last_checked FROM site_watches "
            "WHERE username=? ORDER BY id", (username,)).fetchall()
        return {"ok": True, "watches": [dict(r) for r in rows]}
    finally:
        con.close()
