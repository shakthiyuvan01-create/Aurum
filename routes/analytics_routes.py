"""
routes/analytics_routes.py — Performance Analytics dashboard.
Tracks: response time, model latency, tool success/failure rate,
token usage, memory accuracy, plugin usage, user satisfaction.
"""
from __future__ import annotations
import json, logging, os, sqlite3, time
from flask import Blueprint, request, jsonify, session
from services.auth_service import login_required

analytics_bp = Blueprint("analytics", __name__)
log = logging.getLogger("routes.analytics")

_deps: dict = {}
def _init(deps): _deps.update(deps)

def _db():
    from pathlib import Path
    return str(Path(os.path.abspath(__file__)).parent.parent / "aiaurum.db")


def _ensure_tables():
    con = sqlite3.connect(_db())
    con.executescript("""
    CREATE TABLE IF NOT EXISTS response_analytics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        model TEXT NOT NULL,
        prompt_tokens INTEGER DEFAULT 0,
        completion_tokens INTEGER DEFAULT 0,
        latency_ms INTEGER DEFAULT 0,
        rating INTEGER DEFAULT 0,
        created_at INTEGER DEFAULT (strftime('%s','now'))
    );
    CREATE INDEX IF NOT EXISTS idx_ra_user ON response_analytics(username);
    """)
    con.commit()
    con.close()

_ensure_tables()


@analytics_bp.route("/analytics/record", methods=["POST"])
@login_required
def record():
    """Record a response metric event."""
    data     = request.get_json(force=True) or {}
    username = session.get("username","guest")
    con = sqlite3.connect(_db())
    con.execute(
        "INSERT INTO response_analytics(username,model,prompt_tokens,completion_tokens,latency_ms,rating) VALUES(?,?,?,?,?,?)",
        (username, data.get("model","unknown"), data.get("prompt_tokens",0),
         data.get("completion_tokens",0), data.get("latency_ms",0), data.get("rating",0)),
    )
    con.commit()
    con.close()
    return jsonify({"ok": True})


@analytics_bp.route("/analytics/summary")
@login_required
def summary():
    username = session.get("username","guest")
    days     = int(request.args.get("days","7"))
    since    = int(time.time()) - days * 86400

    con = sqlite3.connect(_db())
    con.row_factory = sqlite3.Row

    # Response analytics
    rows = con.execute(
        "SELECT * FROM response_analytics WHERE username=? AND created_at>? ORDER BY created_at DESC",
        (username, since)
    ).fetchall()
    rows = [dict(r) for r in rows]

    total_requests  = len(rows)
    avg_latency_ms  = round(sum(r["latency_ms"] for r in rows) / max(total_requests,1))
    total_tokens    = sum(r["prompt_tokens"]+r["completion_tokens"] for r in rows)
    rated           = [r["rating"] for r in rows if r["rating"] > 0]
    avg_rating      = round(sum(rated)/len(rated), 2) if rated else 0

    # Model breakdown
    from collections import Counter
    model_counts = Counter(r["model"] for r in rows)

    # Tool metrics
    tool_rows = []
    try:
        tool_rows = [dict(r) for r in con.execute(
            "SELECT tool_name, call_count, success_count, fail_count, avg_latency_ms "
            "FROM tool_metrics WHERE username=? ORDER BY call_count DESC LIMIT 10", (username,)
        ).fetchall()]
    except Exception:
        pass

    # Learned lessons
    lesson_count = 0
    try:
        lesson_count = con.execute(
            "SELECT COUNT(*) FROM learned_lessons WHERE username=?", (username,)
        ).fetchone()[0]
    except Exception:
        pass

    con.close()

    return jsonify({
        "period_days":    days,
        "total_requests": total_requests,
        "avg_latency_ms": avg_latency_ms,
        "total_tokens":   total_tokens,
        "avg_rating":     avg_rating,
        "model_usage":    dict(model_counts),
        "top_tools":      tool_rows,
        "lessons_stored": lesson_count,
    })


@analytics_bp.route("/analytics/lessons")
@login_required
def lessons():
    from services.auto_learn import get_lessons
    username = session.get("username","guest")
    category = request.args.get("category","")
    return jsonify({"lessons": get_lessons(username, category)})


@analytics_bp.route("/analytics/lessons/run", methods=["POST"])
@login_required
def run_learning():
    """Manually trigger the daily learning job."""
    from services.auto_learn import daily_learn_job
    username = session.get("username","guest")
    result   = daily_learn_job(username)
    return jsonify(result)
