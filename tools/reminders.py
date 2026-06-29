"""Reminders tool — create, list, and delete reminders stored in SQLite."""
import os, sqlite3, re, logging
from datetime import datetime

NAME        = "reminders"
DESCRIPTION = "Set, view, and delete reminders with time-based alerts"
CATEGORY    = "builtin"
ICON        = "⏰"
INPUTS = [
    {"name": "action", "label": "Action", "type": "select",
     "options": [{"value": "list",   "label": "View reminders"},
                 {"value": "add",    "label": "Add reminder"},
                 {"value": "delete", "label": "Delete reminder"}],
     "required": True, "default": "list"},
    {"name": "text",     "label": "Reminder", "type": "text",
     "placeholder": "e.g. Call mom, Take medicine", "required": False},
    {"name": "datetime", "label": "When (YYYY-MM-DD HH:MM)", "type": "datetime-local",
     "required": False},
    {"name": "reminder_id", "label": "Reminder ID (to delete)", "type": "number",
     "required": False},
    {"name": "username", "label": "", "type": "hidden", "required": False},
]

log = logging.getLogger("tools.reminders")

BASE    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE, "aiaurum.db")

def _conn():
    c = sqlite3.connect(DB_PATH, check_same_thread=False)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("""
        CREATE TABLE IF NOT EXISTS reminders (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            username   TEXT NOT NULL DEFAULT 'default',
            text       TEXT NOT NULL,
            due_ts     REAL NOT NULL,
            fired      INTEGER DEFAULT 0,
            created_at INTEGER DEFAULT (strftime('%s','now'))
        )
    """)
    return c

def _parse_dt(dt_str: str) -> float | None:
    """Parse ISO-like datetime string to timestamp."""
    if not dt_str:
        return None
    for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(dt_str.strip(), fmt).timestamp()
        except ValueError:
            pass
    return None

def run(action: str = "list", text: str = "", datetime: str = "",
        reminder_id: str = "", username: str = "default") -> dict:
    con = _conn()
    try:
        import time as _time

        if action == "list":
            now = _time.time()
            rows = con.execute(
                "SELECT id,text,due_ts,fired FROM reminders "
                "WHERE username=? AND fired=0 ORDER BY due_ts LIMIT 20",
                (username,)
            ).fetchall()
            reminders = [
                {
                    "id":   r[0],
                    "text": r[1],
                    "due":  _fmt_ts(r[2]),
                    "overdue": r[2] < now,
                }
                for r in rows
            ]
            return {"reminders": reminders, "count": len(reminders)}

        elif action == "add":
            if not text:
                return {"error": "Reminder text is required."}
            due_ts = _parse_dt(datetime)
            if not due_ts:
                return {"error": "Please provide a valid date/time."}
            con.execute(
                "INSERT INTO reminders (username,text,due_ts) VALUES (?,?,?)",
                (username, text.strip(), due_ts)
            )
            con.commit()
            return {"success": True, "text": text, "due": _fmt_ts(due_ts),
                    "message": f"Reminder set: '{text}' at {_fmt_ts(due_ts)}"}

        elif action == "delete":
            if not reminder_id:
                return {"error": "Provide the reminder ID to delete."}
            rid = int(str(reminder_id).strip())
            row = con.execute(
                "SELECT text FROM reminders WHERE id=? AND username=?",
                (rid, username)
            ).fetchone()
            if not row:
                return {"error": f"Reminder #{rid} not found."}
            con.execute("DELETE FROM reminders WHERE id=? AND username=?", (rid, username))
            con.commit()
            return {"success": True, "message": f"Deleted reminder: {row[0]}"}

        else:
            return {"error": f"Unknown action: {action}"}

    except Exception as e:
        log.error("Reminders error: %s", e)
        return {"error": str(e)}
    finally:
        con.close()

def _fmt_ts(ts: float) -> str:
    try:
        return datetime.fromtimestamp(ts).strftime("%a %d %b %Y, %I:%M %p")
    except Exception:
        return str(ts)

def get_due_reminders(username: str) -> list:
    """Called by background watcher — returns reminders that have fired."""
    import time as _t
    con = _conn()
    try:
        rows = con.execute(
            "SELECT id,text FROM reminders WHERE username=? AND fired=0 AND due_ts<=?",
            (username, _t.time())
        ).fetchall()
        if rows:
            ids = [r[0] for r in rows]
            con.execute(
                f"UPDATE reminders SET fired=1 WHERE id IN ({','.join('?'*len(ids))})",
                ids
            )
            con.commit()
        return [{"id": r[0], "text": r[1]} for r in rows]
    except Exception as e:
        log.error("get_due_reminders error: %s", e)
        return []
    finally:
        con.close()
