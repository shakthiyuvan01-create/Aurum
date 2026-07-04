"""
routes/dashboard_routes.py — AI Operating System Dashboard.
Live metrics: CPU, Memory, Tokens, Agents, Tasks, Files, Projects, Plugins, Analytics.
SSE stream for real-time updates.
"""
from __future__ import annotations
import json, logging, os, time
from flask import Blueprint, jsonify, Response, session, stream_with_context, render_template
from services.auth_service import login_required

dashboard_bp = Blueprint("dashboard", __name__)
log = logging.getLogger("routes.dashboard")

_deps: dict = {}

def _init(deps: dict) -> None:
    _deps.update(deps)


def _system_stats() -> dict:
    stats: dict = {}
    try:
        import psutil
        stats["cpu_percent"]  = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()
        stats["ram_percent"]  = mem.percent
        stats["ram_used_gb"]  = round(mem.used / 1e9, 2)
        stats["ram_total_gb"] = round(mem.total / 1e9, 2)
        stats["process_count"]= len(psutil.pids())
        disk = psutil.disk_usage("/")
        stats["disk_used_gb"]  = round(disk.used / 1e9, 2)
        stats["disk_total_gb"] = round(disk.total / 1e9, 2)
        stats["disk_percent"]  = disk.percent
    except ImportError:
        stats.update({"cpu_percent":0,"ram_percent":0,"ram_used_gb":0,"ram_total_gb":0,
                      "process_count":0,"disk_used_gb":0,"disk_total_gb":0,"disk_percent":0})
    return stats


def _token_stats(username: str) -> dict:
    db = _deps.get("db")
    if not db:
        return {"total_tokens": 0, "today_tokens": 0, "cost_usd": 0.0}
    try:
        import sqlite3
        from pathlib import Path
        db_path = str(Path(os.path.abspath(__file__)).parent.parent / "aiaurum.db")
        con = sqlite3.connect(db_path)
        today_start = int(time.time()) - 86400
        total = con.execute(
            "SELECT COALESCE(SUM(tokens_used),0) FROM tool_metrics WHERE username=?", (username,)
        ).fetchone()[0]
        today = con.execute(
            "SELECT COALESCE(SUM(tokens_used),0) FROM tool_metrics WHERE username=? AND last_used>?",
            (username, today_start)
        ).fetchone()[0]
        con.close()
        return {"total_tokens": int(total), "today_tokens": int(today), "cost_usd": round(total * 0.000002, 4)}
    except Exception:
        return {"total_tokens": 0, "today_tokens": 0, "cost_usd": 0.0}


def _agent_stats(username: str) -> dict:
    try:
        import agents as _agents
        return {"available": len(_agents.list_agents()), "running": 0}
    except Exception:
        return {"available": 0, "running": 0}


def _tool_stats() -> dict:
    try:
        import tools as _tools
        tool_list = _tools.list_tools()
        return {"total": len(tool_list), "plugins": len([t for t in tool_list if t.get("plugin")])}
    except Exception:
        return {"total": 0, "plugins": 0}


def _project_stats(username: str) -> dict:
    try:
        import sqlite3
        from pathlib import Path
        db_path = str(Path(os.path.abspath(__file__)).parent.parent / "aiaurum.db")
        con = sqlite3.connect(db_path)
        count = con.execute(
            "SELECT COUNT(*) FROM projects WHERE username=? AND status=\'active\'", (username,)
        ).fetchone()[0]
        con.close()
        return {"active": count}
    except Exception:
        return {"active": 0}


def _workflow_stats(username: str) -> dict:
    try:
        from workflows import list_workflows
        wfs = list_workflows(username)
        return {"total": len(wfs), "enabled": sum(1 for w in wfs if w.get("enabled"))}
    except Exception:
        return {"total": 0, "enabled": 0}


def _recent_logs() -> list[str]:
    try:
        log_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "aurum.log")
        if os.path.exists(log_path):
            with open(log_path) as f:
                lines = f.readlines()
            return [l.strip() for l in lines[-20:] if l.strip()]
    except Exception:
        pass
    return []


@dashboard_bp.route("/dashboard")
@login_required
def dashboard():
    username = session.get("username","guest")
    sys_s  = _system_stats()
    tok_s  = _token_stats(username)
    agt_s  = _agent_stats(username)
    tool_s = _tool_stats()
    proj_s = _project_stats(username)
    wf_s   = _workflow_stats(username)
    return jsonify({
        "system":    sys_s,
        "tokens":    tok_s,
        "agents":    agt_s,
        "tools":     tool_s,
        "projects":  proj_s,
        "workflows": wf_s,
        "timestamp": int(time.time()),
    })


@dashboard_bp.route("/dashboard/stream")
@login_required
def dashboard_stream():
    """SSE stream — pushes dashboard snapshot every 5 seconds."""
    username = session.get("username","guest")

    def generate():
        for _ in range(120):   # max 10 minutes
            try:
                snapshot = {
                    "system":    _system_stats(),
                    "tokens":    _token_stats(username),
                    "agents":    _agent_stats(username),
                    "tools":     _tool_stats(),
                    "timestamp": int(time.time()),
                }
                yield "data: " + json.dumps(snapshot) + "\n\n"
            except Exception as e:
                yield "data: " + json.dumps({"error": str(e)}) + "\n\n"
            time.sleep(5)

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"},
    )


@dashboard_bp.route("/dashboard/logs")
@login_required
def recent_logs():
    return jsonify({"logs": _recent_logs()})


@dashboard_bp.route("/live")
@login_required
def live_dashboard():
    """Full-page live dashboard (SSE system stats + 30s intelligence refresh)."""
    return render_template("dashboard.html")
