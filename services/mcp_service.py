"""services/mcp_service.py - MCP (Model Context Protocol) server management."""
from __future__ import annotations
import json, logging, os, sqlite3
from pathlib import Path
import requests as _rq
log = logging.getLogger("services.mcp_service")
BASE = Path(__file__).resolve().parent.parent
DB_PATH = BASE / "aiaurum.db"

def _ensure():
    con=sqlite3.connect(str(DB_PATH),timeout=10)
    con.execute("CREATE TABLE IF NOT EXISTS mcp_servers(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT UNIQUE,url TEXT,headers TEXT DEFAULT '{}',enabled INTEGER DEFAULT 1,tools_cache TEXT,created_at INTEGER DEFAULT(strftime('%s','now')))")
    con.commit(); con.close()

def connect(name: str, url: str, headers: dict = None) -> dict:
    """Connect to an MCP server and discover its tools."""
    _ensure()
    hdrs = headers or {}
    try:
        r = _rq.post(url.rstrip("/") + "/tools/list", json={}, headers=hdrs, timeout=10)
        if r.status_code != 200:
            return {"error": f"Server returned {r.status_code}"}
        tools = r.json().get("tools", r.json().get("result", []))
        con = sqlite3.connect(str(DB_PATH), timeout=10)
        con.execute("INSERT OR REPLACE INTO mcp_servers(name,url,headers,tools_cache) VALUES(?,?,?,?)",
                    (name, url, json.dumps(hdrs), json.dumps(tools)))
        con.commit(); con.close()
        return {"result": f"Connected to {name}", "tools": tools, "tool_count": len(tools)}
    except Exception as e:
        return {"error": str(e)}

def call_tool(server_name: str, tool_name: str, arguments: dict = None) -> dict:
    """Call a tool on a connected MCP server."""
    _ensure()
    con = sqlite3.connect(str(DB_PATH), timeout=10)
    row = con.execute("SELECT url,headers FROM mcp_servers WHERE name=? AND enabled=1", (server_name,)).fetchone()
    con.close()
    if not row:
        return {"error": f"Server '{server_name}' not found or disabled"}
    try:
        hdrs = json.loads(row[1]) if row[1] else {}
        r = _rq.post(row[0].rstrip("/") + "/tools/call", json={"name": tool_name, "arguments": arguments or {}}, headers=hdrs, timeout=60)
        if r.status_code != 200:
            return {"error": f"Call failed: {r.status_code}"}
        return {"result": r.json()}
    except Exception as e:
        return {"error": str(e)}

def list_servers() -> list:
    """List all configured MCP servers."""
    _ensure()
    con = sqlite3.connect(str(DB_PATH), timeout=10)
    rows = con.execute("SELECT name,url,enabled,tools_cache FROM mcp_servers ORDER BY name").fetchall()
    con.close()
    return [{"name": r[0], "url": r[1], "enabled": bool(r[2]), "tools": json.loads(r[3]) if r[3] else []} for r in rows]

def remove_server(name: str) -> dict:
    """Remove an MCP server connection."""
    _ensure()
    con = sqlite3.connect(str(DB_PATH), timeout=10)
    con.execute("DELETE FROM mcp_servers WHERE name=?", (name,))
    con.commit(); con.close()
    return {"result": f"Server '{name}' removed"}

def disable_server(name: str) -> dict:
    """Disable an MCP server without removing it."""
    _ensure()
    con = sqlite3.connect(str(DB_PATH), timeout=10)
    con.execute("UPDATE mcp_servers SET enabled = CASE WHEN enabled=1 THEN 0 ELSE 1 END WHERE name=?", (name,))
    con.commit(); con.close()
    return {"result": f"Toggled '{name}'"}

def refresh_tools(server_name: str) -> dict:
    """Re-discover tools from an MCP server."""
    _ensure()
    con = sqlite3.connect(str(DB_PATH), timeout=10)
    row = con.execute("SELECT url,headers FROM mcp_servers WHERE name=?", (server_name,)).fetchone()
    con.close()
    if not row:
        return {"error": f"Server '{server_name}' not found"}
    return connect(server_name, row[0], json.loads(row[1]) if row[1] else {})
