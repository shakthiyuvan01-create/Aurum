"""
tools/mission_mode.py -- entire projects as "missions".

create: AI turns a goal into Mission -> Objectives -> Roadmap -> Tasks with
deadlines and budget estimate, stored in SQLite.
list / status / advance: track and update progress.
"""
import json
import os
import sqlite3
import logging

log = logging.getLogger("tools.mission_mode")

NAME        = "mission_mode"
DESCRIPTION = ("AI Mission Mode: turn a big goal into a mission with objectives, "
               "roadmap, tasks, deadlines and budget. Actions: create (goal), "
               "list, status (mission_id), advance (mission_id, task_index).")
CATEGORY = "builtin"
ICON     = "target"
INPUTS = [
    {"name": "action", "label": "Action", "type": "select",
     "options": [{"value": "create", "label": "Create mission"},
                 {"value": "list", "label": "List missions"},
                 {"value": "status", "label": "Mission status"},
                 {"value": "advance", "label": "Complete a task"}], "required": True},
    {"name": "goal",       "label": "Goal (for create)", "type": "textarea"},
    {"name": "mission_id", "label": "Mission ID", "type": "text"},
    {"name": "task_index", "label": "Task number to complete", "type": "text"},
    {"name": "username",   "label": "Username", "type": "text"},
]

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "aiaurum.db")


def _conn():
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("""CREATE TABLE IF NOT EXISTS missions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username   TEXT NOT NULL,
        title      TEXT NOT NULL,
        plan       TEXT NOT NULL,
        tasks      TEXT NOT NULL DEFAULT '[]',
        done       TEXT NOT NULL DEFAULT '[]',
        created_at INTEGER DEFAULT (strftime('%s','now')))""")
    return con


def run(action: str = "list", goal: str = "", mission_id: str = "",
        task_index: str = "", username: str = "default") -> dict:
    action = (action or "list").lower().strip()
    con = _conn()
    try:
        if action == "create":
            if not goal.strip():
                return {"error": "goal required"}
            from providers import AI
            raw = AI.generate(
                "Turn this goal into a mission plan. Reply ONLY JSON:\n"
                '{"title": "...", "mission": "1-line mission statement", '
                '"objectives": ["..."], "roadmap": "phased roadmap text", '
                '"tasks": ["task 1", ...], "deadline_weeks": n, '
                '"budget_estimate": "..."}\n\nGOAL: ' + goal,
                model="gpt-4o", max_tokens=1200, temperature=0.3)
            import re
            m = re.search(r"\{[\s\S]*\}", raw)
            if not m:
                return {"error": "planning failed", "raw": raw[:300]}
            plan = json.loads(m.group(0))
            cur = con.execute(
                "INSERT INTO missions (username, title, plan, tasks) VALUES (?,?,?,?)",
                (username, plan.get("title", goal[:80]), json.dumps(plan),
                 json.dumps(plan.get("tasks", []))))
            con.commit()
            tasks = plan.get("tasks", [])
            return {"ok": True, "mission_id": cur.lastrowid,
                    "result": "# Mission: %s\n\n**%s**\n\n## Objectives\n%s\n\n"
                              "## Roadmap\n%s\n\n## Tasks\n%s\n\nDeadline: ~%s weeks | "
                              "Budget: %s\n\nMission ID: %d" % (
                        plan.get("title", ""), plan.get("mission", ""),
                        "\n".join("- " + o for o in plan.get("objectives", [])),
                        plan.get("roadmap", ""),
                        "\n".join("%d. %s" % (i + 1, t) for i, t in enumerate(tasks)),
                        plan.get("deadline_weeks", "?"),
                        plan.get("budget_estimate", "?"), cur.lastrowid)}

        if action == "list":
            rows = con.execute(
                "SELECT id, title, tasks, done, created_at FROM missions "
                "WHERE username=? ORDER BY id DESC", (username,)).fetchall()
            out = []
            for r in rows:
                total = len(json.loads(r["tasks"]))
                done  = len(json.loads(r["done"]))
                out.append("Mission %d: %s -- %d/%d tasks (%d%%)" % (
                    r["id"], r["title"], done, total,
                    round(100 * done / total) if total else 0))
            return {"result": "\n".join(out) or "No missions yet. Use action=create."}

        row = con.execute("SELECT * FROM missions WHERE id=? AND username=?",
                          (mission_id or 0, username)).fetchone()
        if not row:
            return {"error": "mission not found"}
        tasks = json.loads(row["tasks"]); done = json.loads(row["done"])

        if action == "advance":
            try:
                idx = int(task_index) - 1
                if idx not in done and 0 <= idx < len(tasks):
                    done.append(idx)
                    con.execute("UPDATE missions SET done=? WHERE id=?",
                                (json.dumps(done), row["id"]))
                    con.commit()
            except (ValueError, TypeError):
                return {"error": "task_index must be a number"}

        lines = ["# %s -- %d%% complete" % (
            row["title"], round(100 * len(done) / len(tasks)) if tasks else 0)]
        for i, t in enumerate(tasks):
            lines.append("%s %d. %s" % ("[x]" if i in done else "[ ]", i + 1, t))
        return {"result": "\n".join(lines)}
    finally:
        con.close()
