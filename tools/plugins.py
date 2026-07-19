"""tools/plugins.py - Plugin manager: install, list, remove, MCP, webhooks"""
from __future__ import annotations
import json, os, sqlite3
from pathlib import Path
NAME="plugins"; DESCRIPTION="Install/list/remove plugins, MCP, webhooks, API integrations"
CATEGORY="builtin"; ICON="🔌"
BASE=Path(__file__).resolve().parent.parent; PLUGIN_DIR=BASE/"plugins"
INPUTS=[{"name":"action","type":"str","required":True,"placeholder":"list|install|remove|mcp_connect|mcp_list|mcp_call|webhook_create"},{"name":"name","type":"str"},{"name":"url","type":"str"},{"name":"params","type":"str"}]
def run(action="",name="",url="",params="",**kw):
    a=action.strip().lower()
    if a=="list": return _list()
    if a=="install": return _install(name,url or params)
    if a=="remove": return _remove(name)
    if a=="mcp_connect": return _mcp_con(name,url,params)
    if a=="mcp_list": return _mcp_list()
    if a=="mcp_call": return _mcp_call(name,params)
    if a=="webhook_create": return _wh(name,url,params)
    return {"error":f"Unknown: {action}"}
def _list():
    t=[]
    for f in sorted(PLUGIN_DIR.glob("*.py")):
        if f.name.startswith("__"): continue
        t.append({"name":f.stem,"file":f.name,"size":f.stat().st_size})
    return {"result":t,"count":len(t)}
def _install(name,src):
    try:
        if src.startswith(("http://","https://")):
            import requests; r=requests.get(src,timeout=30)
            if r.status_code!=200: return {"error":f"Download {r.status_code}"}
            code=r.text
        elif os.path.isfile(src):
            with open(src) as f: code=f.read()
        else: return {"error":"URL or file path required"}
        n=name or src.split("/")[-1].replace(".py","")
        p=PLUGIN_DIR/f"plugin_{n}.py"; p.write_text(code,encoding="utf-8")
        try: import tools as _t; _t.reload()
        except: pass
        return {"result":f"Plugin '{n}' installed","file":str(p)}
    except Exception as e: return {"error":str(e)}
def _remove(name):
    for f in PLUGIN_DIR.glob(f"*{name}*.py"):
        if f.name.startswith("__"): continue; f.unlink()
    try: import tools as _t; _t.reload()
    except: pass
    return {"result":f"Removed '{name}'"}
def _mcp_con(name,url,params):
    from services.mcp_service import connect
    return connect(name,url,json.loads(params) if params else {})
def _mcp_list():
    from services.mcp_service import list_servers
    return {"result":list_servers()}
def _mcp_call(name,params):
    from services.mcp_service import call_tool
    a=json.loads(params) if params else {}; tn=a.pop("tool","")
    return call_tool(name,tn,a)
def _wh(name,url,params):
    try:
        con=sqlite3.connect(str(BASE/"aiaurum.db"),timeout=10)
        con.execute("CREATE TABLE IF NOT EXISTS webhooks(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT UNIQUE,url TEXT,config TEXT DEFAULT '{}',created_at INTEGER DEFAULT(strftime('%s','now')))")
        con.execute("INSERT OR REPLACE INTO webhooks(name,url,config) VALUES(?,?,?)",(name,url,params or "{}"))
        con.commit(); con.close()
        return {"result":f"Webhook '{name}' registered","url":url}
    except Exception as e: return {"error":str(e)}
