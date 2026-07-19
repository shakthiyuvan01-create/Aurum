"""tools/productivity.py - Calendar, Email, Reminders, Todo, Notes"""
from __future__ import annotations
import json, os, sqlite3
from datetime import datetime
from pathlib import Path
NAME = "productivity"
DESCRIPTION = "Calendar, email, reminders, to-do lists, note-taking"
CATEGORY = "builtin"
ICON = "📋"
BASE = Path(__file__).resolve().parent.parent
DB_PATH = BASE / "aiaurum.db"
NOTE_DIR = BASE / "notes"
INPUTS = [{"name":"action","type":"str","required":True,"placeholder":"calendar_add|calendar_list|calendar_today|email_send|reminder_set|reminder_list|todo_add|todo_list|todo_done|note_create|note_read|note_list"},{"name":"title","type":"str"},{"name":"text","type":"str"},{"name":"time_str","type":"str"},{"name":"username","type":"str","placeholder":"default"}]

def _db():
    con=sqlite3.connect(str(DB_PATH),timeout=10); con.row_factory=sqlite3.Row; return con
def _ensure():
    con=_db()
    con.execute("CREATE TABLE IF NOT EXISTS calendar(id INTEGER PRIMARY KEY AUTOINCREMENT,username TEXT,title TEXT,description TEXT,event_time TEXT,created_at INTEGER DEFAULT (strftime('%s','now')))")
    con.execute("CREATE TABLE IF NOT EXISTS reminders(id INTEGER PRIMARY KEY AUTOINCREMENT,username TEXT,title TEXT,remind_at TEXT,done INTEGER DEFAULT 0,created_at INTEGER DEFAULT (strftime('%s','now')))")
    con.execute("CREATE TABLE IF NOT EXISTS todos(id INTEGER PRIMARY KEY AUTOINCREMENT,username TEXT,title TEXT,description TEXT,done INTEGER DEFAULT 0, created_at INTEGER DEFAULT (strftime('%s','now')))")
    con.commit(); con.close()

def run(action="",title="",text="",time_str="",username="default"):
    a=action.strip().lower(); _ensure()
    if a=="calendar_add": return _cal_add(title,text,time_str,username)
    if a=="calendar_list": return _cal_list(username)
    if a=="calendar_today": return _cal_today(username)
    if a=="email_send": return _email_send(title,text,username)
    if a=="reminder_set": return _rem_set(title,time_str,username)
    if a=="reminder_list": return _rem_list(username)
    if a=="todo_add": return _todo_add(title,text,username)
    if a=="todo_list": return _todo_list(username)
    if a=="todo_done": return _todo_done(title,username)
    if a=="note_create": return _note_create(title,text,username)
    if a=="note_read": return _note_read(title,username)
    if a=="note_list": return _note_list(username)
    return {"error":f"Unknown: {action}"}

def _cal_add(title,text,time_str,username):
    con=_db()
    con.execute("INSERT INTO calendar(username,title,description,event_time) VALUES(?,?,?,?)",(username,title,text,time_str or datetime.now().isoformat()))
    con.commit(); con.close()
    return {"result":f"Event '{title}' added","time":time_str}

def _cal_list(username):
    con=_db()
    rows=con.execute("SELECT * FROM calendar WHERE username=? ORDER BY event_time DESC LIMIT 50",(username,)).fetchall()
    con.close()
    return {"result":[dict(r) for r in rows],"count":len(rows)}

def _cal_today(username):
    con=_db()
    today=datetime.now().strftime("%Y-%m-%d")
    rows=con.execute("SELECT * FROM calendar WHERE username=? AND event_time LIKE ? ORDER BY event_time",(username,f"{today}%")).fetchall()
    con.close()
    return {"result":[dict(r) for r in rows],"count":len(rows)}

def _email_send(subject,body,username):
    host=os.getenv("SMTP_HOST",""); user=os.getenv("SMTP_USER",""); pw=os.getenv("SMTP_PASS",""); to=os.getenv("SMTP_TO","")
    if not all([host,user,pw,to]): return {"error":"Set SMTP_HOST, SMTP_USER, SMTP_PASS, SMTP_TO in .env"}
    try:
        import smtplib; from email.message import EmailMessage
        msg=EmailMessage(); msg.set_content(body or ""); msg["Subject"]=subject; msg["From"]=user; msg["To"]=to
        with smtplib.SMTP_SSL(host,465) as s: s.login(user,pw); s.send_message(msg)
        return {"result":"Email sent","to":to,"subject":subject}
    except Exception as e: return {"error":str(e)}

def _rem_set(title,time_str,username):
    con=_db()
    con.execute("INSERT INTO reminders(username,title,remind_at) VALUES(?,?,?)",(username,title,time_str or datetime.now().isoformat()))
    con.commit(); con.close()
    return {"result":f"Reminder '{title}' at {time_str}"}

def _rem_list(username):
    con=_db()
    rows=con.execute("SELECT * FROM reminders WHERE username=? AND done=0 ORDER BY remind_at LIMIT 50",(username,)).fetchall()
    con.close()
    return {"result":[dict(r) for r in rows],"count":len(rows)}

def _todo_add(title,text,username):
    con=_db()
    con.execute("INSERT INTO todos(username,title,description) VALUES(?,?,?)",(username,title,text))
    con.commit(); con.close()
    return {"result":f"Todo '{title}' added"}

def _todo_list(username):
    con=_db()
    rows=con.execute("SELECT * FROM todos WHERE username=? ORDER BY done,created_at DESC",(username,)).fetchall()
    con.close()
    return {"result":[dict(r) for r in rows],"count":len(rows)}

def _todo_done(title,username):
    con=_db()
    con.execute("UPDATE todos SET done=1 WHERE username=? AND title=? AND done=0",(username,title))
    con.commit(); con.close()
    return {"result":f"Todo '{title}' completed"}

def _note_create(title,text,username):
    NOTE_DIR.mkdir(parents=True,exist_ok=True)
    safe="".join(c for c in title if c.isalnum() or c in " _-")[:60]
    p=NOTE_DIR/f"{username}_{safe}.md"
    p.write_text(f"# {title}\n\n{text or ''}\n\n---\nCreated: {datetime.now().isoformat()}\nUser: {username}",encoding="utf-8")
    return {"result":f"Note '{title}' saved","file":str(p)}

def _note_read(title,username):
    NOTE_DIR.mkdir(parents=True,exist_ok=True)
    safe="".join(c for c in title if c.isalnum() or c in " _-")[:60]
    p=NOTE_DIR/f"{username}_{safe}.md"
    if not p.is_file():
        for m in NOTE_DIR.glob(f"{username}_*.md"):
            if title.lower() in m.stem.lower(): return {"result":m.read_text(encoding="utf-8"),"file":str(m)}
        return {"error":f"Note '{title}' not found"}
    return {"result":p.read_text(encoding="utf-8"),"file":str(p)}

def _note_list(username):
    NOTE_DIR.mkdir(parents=True,exist_ok=True)
    notes=[{"name":f.stem.replace(f"{username}_",""),"file":str(f),"size":f.stat().st_size} for f in sorted(NOTE_DIR.glob(f"{username}_*.md"))]
    return {"result":notes,"count":len(notes)}
