"""
routes/workspace_routes.py — Workspace / Projects system.
Each project stores: Files, Memory, Goals, Chat, Knowledge, Code, Documents, Tasks.
Like ChatGPT Projects but with full agent integration.
"""
from __future__ import annotations
import json, logging, os, sqlite3, time, uuid
from contextlib import contextmanager
from flask import Blueprint, request, jsonify, session
from services.auth_service import login_required

workspace_bp = Blueprint("workspace", __name__)
log = logging.getLogger("routes.workspace")

_deps: dict = {}

def _init(deps: dict) -> None:
    _deps.update(deps)


def _db_path():
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "aiaurum.db")


@contextmanager
def _conn():
    con = sqlite3.connect(_db_path())
    con.row_factory = sqlite3.Row
    con.executescript("""
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            username TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT DEFAULT \'\',
            goals TEXT DEFAULT \'[]\',
            tech_stack TEXT DEFAULT \'[]\',
            status TEXT DEFAULT \'active\',
            created_at INTEGER DEFAULT (strftime('%s','now')),
            updated_at INTEGER DEFAULT (strftime('%s','now'))
        );
        CREATE TABLE IF NOT EXISTS project_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT NOT NULL,
            username TEXT NOT NULL,
            filename TEXT NOT NULL,
            filepath TEXT NOT NULL,
            size INTEGER DEFAULT 0,
            uploaded_at INTEGER DEFAULT (strftime('%s','now'))
        );
        CREATE TABLE IF NOT EXISTS project_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT NOT NULL,
            username TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT DEFAULT \'\',
            status TEXT DEFAULT \'pending\',
            priority TEXT DEFAULT \'medium\',
            due_date TEXT DEFAULT \'\',
            created_at INTEGER DEFAULT (strftime('%s','now'))
        );
        CREATE TABLE IF NOT EXISTS project_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT NOT NULL,
            username TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at INTEGER DEFAULT (strftime('%s','now'))
        );
    """)
    con.commit()
    try:
        yield con
        con.commit()
    finally:
        con.close()


# ── Projects CRUD ─────────────────────────────────────────────────────────────
@workspace_bp.route("/workspace/projects", methods=["GET"])
@login_required
def list_projects():
    username = session["username"]
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM projects WHERE username=? ORDER BY updated_at DESC", (username,)
        ).fetchall()
        projects = []
        for row in rows:
            d = dict(row)
            d["goals"]      = json.loads(d.get("goals", "[]"))
            d["tech_stack"] = json.loads(d.get("tech_stack", "[]"))
            # Counts
            d["file_count"] = con.execute(
                "SELECT COUNT(*) FROM project_files WHERE project_id=?", (d["id"],)
            ).fetchone()[0]
            d["task_count"] = con.execute(
                "SELECT COUNT(*) FROM project_tasks WHERE project_id=? AND status!=\'done\'", (d["id"],)
            ).fetchone()[0]
            projects.append(d)
    return jsonify({"projects": projects})


@workspace_bp.route("/workspace/projects", methods=["POST"])
@login_required
def create_project():
    username = session["username"]
    data     = request.get_json(force=True) or {}
    name     = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name required"}), 400
    pid = uuid.uuid4().hex[:12]
    with _conn() as con:
        con.execute(
            "INSERT INTO projects(id,username,name,description,goals,tech_stack) VALUES(?,?,?,?,?,?)",
            (pid, username, name,
             data.get("description",""),
             json.dumps(data.get("goals",[])),
             json.dumps(data.get("tech_stack",[]))),
        )
    return jsonify({"id": pid, "name": name}), 201


@workspace_bp.route("/workspace/projects/<pid>", methods=["GET"])
@login_required
def get_project(pid: str):
    username = session["username"]
    with _conn() as con:
        row = con.execute("SELECT * FROM projects WHERE id=? AND username=?", (pid, username)).fetchone()
        if not row:
            return jsonify({"error": "Not found"}), 404
        d = dict(row)
        d["goals"]      = json.loads(d.get("goals","[]"))
        d["tech_stack"] = json.loads(d.get("tech_stack","[]"))
        d["files"]      = [dict(r) for r in con.execute(
            "SELECT * FROM project_files WHERE project_id=? ORDER BY uploaded_at DESC", (pid,))]
        d["tasks"]      = [dict(r) for r in con.execute(
            "SELECT * FROM project_tasks WHERE project_id=? ORDER BY created_at DESC", (pid,))]
        d["notes"]      = [dict(r) for r in con.execute(
            "SELECT * FROM project_notes WHERE project_id=? ORDER BY created_at DESC LIMIT 20", (pid,))]
    return jsonify(d)


@workspace_bp.route("/workspace/projects/<pid>", methods=["PUT"])
@login_required
def update_project(pid: str):
    username = session["username"]
    data     = request.get_json(force=True) or {}
    with _conn() as con:
        con.execute(
            "UPDATE projects SET name=COALESCE(?,name), description=COALESCE(?,description), "
            "goals=COALESCE(?,goals), tech_stack=COALESCE(?,tech_stack), "
            "status=COALESCE(?,status), updated_at=? WHERE id=? AND username=?",
            (
                data.get("name"), data.get("description"),
                json.dumps(data["goals"]) if "goals" in data else None,
                json.dumps(data["tech_stack"]) if "tech_stack" in data else None,
                data.get("status"), int(time.time()), pid, username,
            ),
        )
    return jsonify({"ok": True})


@workspace_bp.route("/workspace/projects/<pid>", methods=["DELETE"])
@login_required
def delete_project(pid: str):
    username = session["username"]
    with _conn() as con:
        con.execute("DELETE FROM projects WHERE id=? AND username=?", (pid, username))
        con.execute("DELETE FROM project_files  WHERE project_id=?", (pid,))
        con.execute("DELETE FROM project_tasks  WHERE project_id=?", (pid,))
        con.execute("DELETE FROM project_notes  WHERE project_id=?", (pid,))
    return jsonify({"ok": True})


# ── Project tasks ─────────────────────────────────────────────────────────────
@workspace_bp.route("/workspace/projects/<pid>/tasks", methods=["POST"])
@login_required
def add_task(pid: str):
    username = session["username"]
    data     = request.get_json(force=True) or {}
    title    = (data.get("title") or "").strip()
    if not title:
        return jsonify({"error": "title required"}), 400
    with _conn() as con:
        cur = con.execute(
            "INSERT INTO project_tasks(project_id,username,title,description,priority,due_date) VALUES(?,?,?,?,?,?)",
            (pid, username, title, data.get("description",""),
             data.get("priority","medium"), data.get("due_date","")),
        )
    return jsonify({"id": cur.lastrowid, "title": title}), 201


@workspace_bp.route("/workspace/projects/<pid>/tasks/<int:tid>", methods=["PUT"])
@login_required
def update_task(pid: str, tid: int):
    data = request.get_json(force=True) or {}
    with _conn() as con:
        con.execute(
            "UPDATE project_tasks SET status=COALESCE(?,status), title=COALESCE(?,title) WHERE id=? AND project_id=?",
            (data.get("status"), data.get("title"), tid, pid),
        )
    return jsonify({"ok": True})


# ── Project notes ─────────────────────────────────────────────────────────────
@workspace_bp.route("/workspace/projects/<pid>/notes", methods=["POST"])
@login_required
def add_note(pid: str):
    username = session["username"]
    data     = request.get_json(force=True) or {}
    content  = (data.get("content") or "").strip()
    if not content:
        return jsonify({"error": "content required"}), 400
    with _conn() as con:
        cur = con.execute(
            "INSERT INTO project_notes(project_id,username,content) VALUES(?,?,?)",
            (pid, username, content),
        )
    return jsonify({"id": cur.lastrowid}), 201


# ── AI project actions ─────────────────────────────────────────────────────────
@workspace_bp.route("/workspace/projects/<pid>/plan", methods=["POST"])
@login_required
def plan_project(pid: str):
    """Use the planning engine to build a task list for this project."""
    username = session["username"]
    with _conn() as con:
        row = con.execute("SELECT * FROM projects WHERE id=? AND username=?", (pid, username)).fetchone()
        if not row:
            return jsonify({"error": "Not found"}), 404
        d = dict(row)

    goal = f"Build: {d['name']}. {d['description']}"
    from planning.planner import create_plan
    plan = create_plan(goal, username)

    # Auto-add steps as tasks
    with _conn() as con:
        for step in plan.steps:
            con.execute(
                "INSERT INTO project_tasks(project_id,username,title,description,priority) VALUES(?,?,?,?,?)",
                (pid, username, step.description[:100], f"Agent: {step.agent}", "medium"),
            )

    return jsonify({"ok": True, "plan": plan.to_dict(), "tasks_added": len(plan.steps)})
