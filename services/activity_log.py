"""
services/activity_log.py -- persisted task history + agent logs.

Two SQLite tables (in aiaurum.db):
  task_history  -- every team run / async tool job (what, who, result, duration)
  agent_logs    -- every agent/team/tool event from the event bus

Wired to the event bus at startup via init_subscribers().
"""
import json
import os
import sqlite3
import time
import logging

log = logging.getLogger("services.activity_log")

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "aiaurum.db")


def _conn():
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    return con


def init_tables():
    with _conn() as con:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS task_history (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                username   TEXT NOT NULL,
                kind       TEXT NOT NULL,          -- team | tool | job
                title      TEXT NOT NULL,
                detail     TEXT DEFAULT '',
                status     TEXT DEFAULT 'done',    -- done | failed
                duration   REAL DEFAULT 0,
                created_at INTEGER DEFAULT (strftime('%s','now'))
            );
            CREATE TABLE IF NOT EXISTS agent_logs (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                username   TEXT DEFAULT '',
                event      TEXT NOT NULL,
                agent      TEXT DEFAULT '',
                payload    TEXT DEFAULT '',
                created_at INTEGER DEFAULT (strftime('%s','now'))
            );
            CREATE INDEX IF NOT EXISTS idx_hist_user ON task_history(username, created_at);
            CREATE INDEX IF NOT EXISTS idx_logs_user ON agent_logs(username, created_at);
        """)


def record_task(username: str, kind: str, title: str, detail: str = "",
                status: str = "done", duration: float = 0):
    try:
        with _conn() as con:
            con.execute(
                "INSERT INTO task_history (username, kind, title, detail, status, duration)"
                " VALUES (?,?,?,?,?,?)",
                (username, kind, title[:300], detail[:2000], status, duration))
    except Exception as e:
        log.warning("record_task: %s", e)


def get_history(username: str, limit: int = 50) -> list:
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM task_history WHERE username=? ORDER BY created_at DESC LIMIT ?",
            (username, limit)).fetchall()
    return [dict(r) for r in rows]


def record_event(event: str, data: dict):
    try:
        with _conn() as con:
            con.execute(
                "INSERT INTO agent_logs (username, event, agent, payload) VALUES (?,?,?,?)",
                ((data or {}).get("username", ""), event,
                 (data or {}).get("agent", "") or (data or {}).get("from", ""),
                 json.dumps(data, default=str)[:2000]))
    except Exception as e:
        log.warning("record_event: %s", e)


def get_logs(username: str = "", limit: int = 100, event_prefix: str = "") -> list:
    q = "SELECT * FROM agent_logs WHERE 1=1"
    args = []
    if username:
        q += " AND username=?"; args.append(username)
    if event_prefix:
        q += " AND event LIKE ?"; args.append(event_prefix + "%")
    q += " ORDER BY created_at DESC LIMIT ?"; args.append(limit)
    with _conn() as con:
        rows = con.execute(q, args).fetchall()
    return [dict(r) for r in rows]


def init_subscribers():
    """Persist agent/team/tool events from the event bus."""
    init_tables()
    try:
        from services.event_bus import bus

        for ev in ("team.started", "team.step.started", "team.step.completed",
                   "team.completed", "agent.message", "agent.completed",
                   "tool.completed", "task.completed"):
            def _make(ev_name):
                def _handler(data):
                    record_event(ev_name, data or {})
                return _handler
            bus.on(ev, _make(ev))
        log.info("activity_log: bus subscribers registered")
    except Exception as e:
        log.warning("activity_log subscribers failed: %s", e)
