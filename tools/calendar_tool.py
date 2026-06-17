"""Calendar tool — local event management stored in SQLite."""
import os, sqlite3, logging
from datetime import date as _date, datetime

NAME        = "calendar"
DESCRIPTION = "Add, view, and delete calendar events stored locally"
CATEGORY    = "builtin"
ICON        = "📅"
INPUTS = [
    {"name": "action",      "label": "Action", "type": "select",
     "options": [{"value": "list",   "label": "View upcoming events"},
                 {"value": "add",    "label": "Add event"},
                 {"value": "delete", "label": "Delete event"}],
     "required": True, "default": "list"},
    {"name": "title",       "label": "Event Title", "type": "text",
     "placeholder": "Meeting with team", "required": False},
    {"name": "date",        "label": "Date (YYYY-MM-DD)", "type": "date",
     "required": False},
    {"name": "time",        "label": "Time (HH:MM)", "type": "time",
     "required": False},
    {"name": "description", "label": "Notes", "type": "text",
     "placeholder": "Optional notes", "required": False},
    {"name": "event_id",    "label": "Event ID (to delete)", "type": "number",
     "required": False},
    {"name": "username",    "label": "", "type": "hidden", "required": False},
]

log = logging.getLogger("tools.calendar")

BASE    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE, "assistneo.db")

def _conn():
    c = sqlite3.connect(DB_PATH, check_same_thread=False)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("""
        CREATE TABLE IF NOT EXISTS calendar_events (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            username    TEXT NOT NULL DEFAULT 'default',
            title       TEXT NOT NULL,
            date        TEXT NOT NULL,
            time        TEXT DEFAULT '',
            description TEXT DEFAULT '',
            created_at  INTEGER DEFAULT (strftime('%s','now'))
        )
    """)
    return c

def run(action: str = "list", title: str = "", date: str = "",
        time: str = "", description: str = "", event_id: str = "",
        username: str = "default") -> dict:

    con = _conn()
    try:
        if action == "list":
            today = _date.today().isoformat()
            rows = con.execute(
                "SELECT id,title,date,time,description FROM calendar_events "
                "WHERE username=? AND date>=? ORDER BY date,time LIMIT 30",
                (username, today)
            ).fetchall()
            events = [{"id": r[0], "title": r[1], "date": r[2],
                       "time": r[3], "description": r[4]} for r in rows]
            return {"events": events, "count": len(events)}

        elif action == "add":
            if not title:
                return {"error": "Event title is required."}
            if not date:
                date = _date.today().isoformat()
            con.execute(
                "INSERT INTO calendar_events (username,title,date,time,description) VALUES (?,?,?,?,?)",
                (username, title.strip(), date, time.strip(), description.strip())
            )
            con.commit()
            when = f"{date} {time}".strip()
            return {"success": True, "title": title, "date": date, "time": time,
                    "message": f"Added '{title}' on {when}"}

        elif action == "delete":
            if not event_id:
                return {"error": "Provide the event ID to delete."}
            eid = int(str(event_id).strip())
            row = con.execute(
                "SELECT title FROM calendar_events WHERE id=? AND username=?",
                (eid, username)
            ).fetchone()
            if not row:
                return {"error": f"Event #{eid} not found."}
            con.execute("DELETE FROM calendar_events WHERE id=? AND username=?", (eid, username))
            con.commit()
            return {"success": True, "message": f"Deleted event: {row[0]}"}

        else:
            return {"error": f"Unknown action: {action}"}

    except Exception as e:
        log.error("Calendar error: %s", e)
        return {"error": str(e)}
    finally:
        con.close()
