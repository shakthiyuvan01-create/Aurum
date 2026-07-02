"""
routes/admin.py — Admin-only routes
=====================================
All routes require role == "admin".

Endpoints:
    GET  /admin/users              — list all users
    POST /admin/users/<un>/role    — set a user's role
    POST /admin/users/<un>/delete  — delete a user
    GET  /admin/metrics            — tool performance metrics
    POST /admin/metrics/<tool>/reset — reset one tool's counters
"""
import logging
from flask import Blueprint, jsonify, request
from services.auth_service import require_role, current_user

admin_bp = Blueprint("admin", __name__)
log = logging.getLogger("routes.admin")

_deps: dict = {}

def _init(deps: dict) -> None:
    _deps.update(deps)

def _db():
    return _deps["db"]


# ── User management ───────────────────────────────────────────────────────────

@admin_bp.route("/admin/users", methods=["GET"])
@require_role("admin")
def admin_list_users():
    log.info("admin_list_users: by=%s", current_user())
    return jsonify({"users": _db().list_all_users()})


@admin_bp.route("/admin/users/<username>/role", methods=["POST"])
@require_role("admin")
def admin_set_role(username: str):
    body = request.get_json(force=True) or {}
    role = (body.get("role") or "").strip().lower()
    if role not in ("user", "admin", "readonly"):
        return jsonify({"error": "role must be user | admin | readonly"}), 400
    _db().set_user_role(username, role)
    log.info("admin_set_role: %s → %s by %s", username, role, current_user())
    return jsonify({"ok": True, "username": username, "role": role})


@admin_bp.route("/admin/users/<username>/delete", methods=["POST"])
@require_role("admin")
def admin_delete_user(username: str):
    if username == current_user():
        return jsonify({"error": "Cannot delete yourself"}), 400
    db = _db()
    user = db.get_user(username)
    if not user:
        return jsonify({"error": "User not found"}), 404
    # remove memories + chats
    db.clear_memories(username)
    for chat in db.list_chats(username):
        db.delete_chat(chat["id"], username)
    import sqlite3 as _sl
    with _sl.connect(db.DB_PATH, check_same_thread=False) as con:
        con.execute("DELETE FROM users WHERE username=?", (username,))
    log.info("admin_delete_user: %s deleted by %s", username, current_user())
    return jsonify({"ok": True})


# ── Tool metrics ──────────────────────────────────────────────────────────────

@admin_bp.route("/admin/metrics", methods=["GET"])
@require_role("admin")
def admin_metrics():
    try:
        from tools.tool_metrics import get_metrics
        return jsonify({"metrics": get_metrics()})
    except Exception as e:
        log.warning("admin_metrics error: %s", e)
        return jsonify({"metrics": {}, "error": str(e)})


@admin_bp.route("/admin/metrics/<tool_name>/reset", methods=["POST"])
@require_role("admin")
def admin_reset_metric(tool_name: str):
    try:
        from tools.tool_metrics import reset_metrics
        reset_metrics(tool_name)
        log.info("admin_reset_metric: %s reset by %s", tool_name, current_user())
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@admin_bp.route("/self_improve/run", methods=["POST"])
@require_role("admin")
def self_improve_run():
    """Manually trigger the safeguarded self-improvement review."""
    from services.self_improve import run_review
    return jsonify(run_review(force=True))


@admin_bp.route("/self_improve/report")
@require_role("admin")
def self_improve_report():
    from services.self_improve import get_reports
    return jsonify({"reports": get_reports()})
