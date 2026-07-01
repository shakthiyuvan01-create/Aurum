"""
routes/subagent_routes.py — Parallel Sub-Agent endpoint for AI Aurum
"""
from __future__ import annotations
import json, logging
from flask import Blueprint, request, session, jsonify, Response, stream_with_context
from services.auth_service import login_required, no_guests

subagent_bp = Blueprint("subagent", __name__)
log = logging.getLogger("routes.subagent")

_deps: dict = {}

def _init(deps: dict) -> None:
    _deps.update(deps)

def _asst():      return _deps["assistant"]
def _subagent():  return _deps["subagent"]


@subagent_bp.route("/subagent", methods=["POST"])
@login_required
@no_guests
def run_subagent():
    data      = request.get_json(force=True) or {}
    task      = (data.get("task") or "").strip()
    n_agents  = int(data.get("n_agents") or 3)
    sub_tasks = data.get("sub_tasks")  # optional manual decomposition

    if not task:
        return jsonify({"error": "task is required"}), 400

    token = _asst().GITHUB_TOKEN or ""
    model = _asst().GITHUB_MODEL

    def generate():
        try:
            for chunk in _subagent().run_parallel(
                task=task, token=token, model=model,
                n_agents=n_agents, sub_tasks=sub_tasks,
            ):
                yield chunk
        except Exception as e:
            log.error("subagent stream error: %s", e)
            yield "data: " + json.dumps({"error": str(e)}) + "\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control":  "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@subagent_bp.route("/subagent/status")
@login_required
def subagent_status():
    return jsonify({"available": True, "max_agents": 6})
