"""routes/planning_routes.py — Autonomous planning API."""
import json, logging
from flask import Blueprint, request, jsonify, Response, session, stream_with_context
from services.auth_service import login_required

planning_bp = Blueprint("planning", __name__)
log = logging.getLogger("routes.planning")

_deps: dict = {}

def _init(deps: dict) -> None:
    _deps.update(deps)


@planning_bp.route("/plan", methods=["POST"])
@login_required
def plan_and_execute():
    """
    SSE endpoint: understand goal → plan → execute → verify → deliver.
    """
    data     = request.get_json(force=True) or {}
    goal     = (data.get("goal") or data.get("message") or "").strip()
    username = session.get("username", "guest")
    if not goal:
        return jsonify({"error": "goal required"}), 400

    from planning.executor import stream_execute

    def generate():
        for event in stream_execute(goal, username):
            yield "data: " + json.dumps(event) + "\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@planning_bp.route("/plan/preview", methods=["POST"])
@login_required
def plan_preview():
    """Return plan without executing it."""
    data = request.get_json(force=True) or {}
    goal = (data.get("goal") or "").strip()
    if not goal:
        return jsonify({"error": "goal required"}), 400
    from planning.planner import create_plan
    plan = create_plan(goal, session.get("username", "guest"))
    return jsonify(plan.to_dict())
