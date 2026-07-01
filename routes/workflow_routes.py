"""routes/workflow_routes.py — AI Workflow Builder API."""
import json, logging
from flask import Blueprint, request, jsonify, session
from services.auth_service import login_required

workflow_bp = Blueprint("workflow", __name__)
log = logging.getLogger("routes.workflow")

_deps: dict = {}

def _init(deps: dict) -> None:
    _deps.update(deps)


@workflow_bp.route("/workflows", methods=["GET"])
@login_required
def list_workflows():
    from workflows import list_workflows as _list
    username = session.get("username", "guest")
    return jsonify({"workflows": _list(username)})


@workflow_bp.route("/workflows", methods=["POST"])
@login_required
def create_workflow():
    from workflows import create_workflow as _create, workflow_from_description as _gen
    data     = request.get_json(force=True) or {}
    username = session.get("username", "guest")

    # AI-generated from description
    if data.get("generate") and data.get("description"):
        result = _gen(data["description"], username)
        return jsonify(result)

    # Manual creation
    wf = _create(
        username    = username,
        name        = data.get("name", "Untitled"),
        description = data.get("description", ""),
        steps       = data.get("steps", []),
        schedule    = data.get("schedule", ""),
    )
    return jsonify(wf), 201


@workflow_bp.route("/workflows/<wf_id>", methods=["GET"])
@login_required
def get_workflow(wf_id: str):
    from workflows import get_workflow as _get
    wf = _get(wf_id, session.get("username", "guest"))
    if not wf:
        return jsonify({"error": "Not found"}), 404
    return jsonify(wf)


@workflow_bp.route("/workflows/<wf_id>/run", methods=["POST"])
@login_required
def run_workflow(wf_id: str):
    from workflows import run_workflow as _run
    data   = request.get_json(force=True) or {}
    result = _run(wf_id, session.get("username","guest"), trigger_data=data.get("data",{}))
    return jsonify(result)


@workflow_bp.route("/workflows/<wf_id>", methods=["DELETE"])
@login_required
def delete_workflow(wf_id: str):
    from workflows import delete_workflow as _del
    ok = _del(wf_id, session.get("username","guest"))
    return jsonify({"ok": ok})
