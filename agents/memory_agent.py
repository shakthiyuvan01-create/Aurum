"""agents/memory_agent.py - Dedicated memory management agent."""
from __future__ import annotations
import json, logging, os, sqlite3
from datetime import datetime
from pathlib import Path
log = logging.getLogger("agents.memory_agent")
BASE = Path(__file__).resolve().parent.parent
DB_PATH = BASE / "aiaurum.db"

NAME = "memory_agent"
DESCRIPTION = "Manages all memory systems: conversations, preferences, knowledge base, semantic search, vector DB"
CATEGORY = "agent"
ICON = "🧠"
INPUTS = [
    {"name":"action","type":"str","required":True,"placeholder":"store|recall|search|summarize|forget|stats|consolidate"},
    {"name":"key","type":"str","placeholder":"Memory key or query"},
    {"name":"value","type":"str","placeholder":"Value to store"},
    {"name":"username","type":"str","placeholder":"default"},
    {"name":"limit","type":"int","placeholder":"10"},
]

def run(action="",key="",value="",username="default",limit=10,**kw):
    a=action.strip().lower()
    if a=="store": return _store(key,value,username)
    if a=="recall": return _recall(key,username)
    if a=="search": return _search(key,username,limit)
    if a=="summarize": return _summarize(username)
    if a=="forget": return _forget(key,username)
    if a=="stats": return _stats(username)
    if a=="consolidate": return _consolidate(username)
    return {"error":f"Unknown: {action}"}

def _ensure():
    con=sqlite3.connect(str(DB_PATH),timeout=10)
    con.execute("CREATE TABLE IF NOT EXISTS memory_store(id INTEGER PRIMARY KEY AUTOINCREMENT,username TEXT,key TEXT,value TEXT,category TEXT DEFAULT 'general',created_at INTEGER DEFAULT(strftime('%s','now')),updated_at INTEGER DEFAULT(strftime('%s','now')))")
    con.execute("CREATE INDEX IF NOT EXISTS idx_mem_key ON memory_store(username,key)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_mem_search ON memory_store(value)")
    con.commit(); con.close()

def _store(key,value,username):
    _ensure(); con=sqlite3.connect(str(DB_PATH),timeout=10)
    existing=con.execute("SELECT id FROM memory_store WHERE username=? AND key=?",(username,key)).fetchone()
    if existing:
        con.execute("UPDATE memory_store SET value=?,updated_at=strftime('%s','now') WHERE id=?",(value,existing[0]))
    else:
        con.execute("INSERT INTO memory_store(username,key,value) VALUES(?,?,?)",(username,key,value))
    con.commit(); con.close()
    try:
        from services.persona import append_daily_log
        append_daily_log(f"Memory: stored '{key}' for {username}")
    except: pass
    return {"result":f"Stored '{key}'","key":key}

def _recall(key,username):
    _ensure(); con=sqlite3.connect(str(DB_PATH),timeout=10)
    rows=con.execute("SELECT value,updated_at FROM memory_store WHERE username=? AND (key=? OR key LIKE ?)",(username,key,f"%{key}%")).fetchall()
    con.close()
    if not rows: return {"result":"","found":False}
    return {"result":rows[0][0],"found":True,"updated_at":rows[0][1],"count":len(rows)}

def _search(query,username,limit=10):
    _ensure(); con=sqlite3.connect(str(DB_PATH),timeout=10)
    rows=con.execute("SELECT key,value,category FROM memory_store WHERE username=? AND (key LIKE ? OR value LIKE ?) LIMIT ?",(username,f"%{query}%",f"%{query}%",limit)).fetchall()
    con.close()
    return {"result":[{"key":r[0],"value":r[1][:500],"category":r[2]} for r in rows],"count":len(rows)}

def _summarize(username):
    _ensure(); con=sqlite3.connect(str(DB_PATH),timeout=10)
    rows=con.execute("SELECT key,category,count(*) as cnt FROM memory_store WHERE username=? GROUP BY category,key ORDER BY category LIMIT 100",(username,)).fetchall()
    con.close()
    total=sum(r[2] for r in rows)
    return {"result":[{"key":r[0],"category":r[1],"count":r[2]} for r in rows],"total_entries":total}

def _forget(key,username):
    _ensure(); con=sqlite3.connect(str(DB_PATH),timeout=10)
    con.execute("DELETE FROM memory_store WHERE username=? AND (key=? OR key LIKE ?)",(username,key,f"%{key}%"))
    deleted=con.rowcount; con.commit(); con.close()
    return {"result":f"Deleted {deleted} entries","deleted":deleted}

def _stats(username):
    _ensure(); con=sqlite3.connect(str(DB_PATH),timeout=10)
    total=con.execute("SELECT count(*) FROM memory_store WHERE username=?",(username,)).fetchone()[0]
    cats=con.execute("SELECT category,count(*) FROM memory_store WHERE username=? GROUP BY category",(username,)).fetchall()
    con.close()
    return {"result":{"total_entries":total,"categories":{r[0]:r[1] for r in cats}},"total":total}

def _consolidate(username):
    """Consolidate recent memories into persona MEMORY.md via the persona system."""
    _ensure()
    recent=_search("","",20).get("result",[])
    if not recent: return {"result":"No memories to consolidate"}
    facts="\n".join(f"- {m['key']}: {m['value']}" for m in recent)
    try:
        from providers import AI
        summary=AI.generate(f"Summarize these memories into a concise MEMORY.md update:\n{facts}",max_tokens=500,temperature=0.2)
        if summary and not summary.startswith("[AI error"):
            from services.persona import write as _pw
            _pw("MEMORY.md",summary,by_ai=True)
            return {"result":"Memories consolidated into MEMORY.md","facts":len(recent)}
    except Exception as e:
        return {"error":str(e)}
    return {"result":"Consolidation skipped"}
