"""
services/dynamic_agents.py -- agents that create new agents.

When the CEO routes work to a specialist that does not exist (say "cfo" or
"legal"), AI Aurum hires one: generates a role + system prompt, stores it,
and from then on that agent is a real, routable employee.
"""
import os
import sqlite3
import logging

log = logging.getLogger("services.dynamic_agents")

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "aiaurum.db")
MAX_CUSTOM = 25


def _conn():
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("""CREATE TABLE IF NOT EXISTS custom_agents (
        name       TEXT PRIMARY KEY,
        title      TEXT NOT NULL,
        prompt     TEXT NOT NULL,
        model      TEXT DEFAULT 'gpt-4o-mini',
        hired_by   TEXT DEFAULT 'ceo',
        created_at INTEGER DEFAULT (strftime('%s','now')))""")
    return con


def get(name: str):
    with _conn() as con:
        r = con.execute("SELECT * FROM custom_agents WHERE name=?",
                        (name.lower().strip(),)).fetchone()
    return dict(r) if r else None


def list_all() -> list:
    with _conn() as con:
        return [dict(r) for r in con.execute(
            "SELECT name, title, model, created_at FROM custom_agents ORDER BY name")]


def hire(name: str, need: str = "") -> dict:
    """Create a new specialist agent for an unmet need."""
    name = "".join(c for c in name.lower().strip() if c.isalnum() or c == "_")[:30]
    if not name:
        return {"error": "invalid name"}
    existing = get(name)
    if existing:
        return existing
    with _conn() as con:
        if con.execute("SELECT COUNT(*) FROM custom_agents").fetchone()[0] >= MAX_CUSTOM:
            return {"error": "custom agent limit reached (%d)" % MAX_CUSTOM}
    from providers import AI
    prompt = AI.generate(
        "Write a system prompt (3-5 sentences) for a new AI specialist agent "
        "named '%s'%s. Define its expertise, working style, and output format. "
        "Also give a 2-4 word job title on the FIRST line, then the prompt."
        % (name, (" needed for: " + need) if need else ""),
        model="gpt-4o-mini", max_tokens=250, temperature=0.4)
    lines = prompt.strip().splitlines()
    title = lines[0].strip("# ").strip()[:40] if lines else name.capitalize()
    body  = "\n".join(lines[1:]).strip() or prompt
    with _conn() as con:
        con.execute("INSERT OR IGNORE INTO custom_agents (name, title, prompt) VALUES (?,?,?)",
                    (name, title, body))
    log.info("hired new agent: %s (%s)", name, title)
    return {"name": name, "title": title, "prompt": body, "model": "gpt-4o-mini"}
