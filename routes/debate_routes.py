"""routes/debate_routes.py — Multi-agent debate endpoint."""
import json
import logging

from flask import Blueprint, request, jsonify, Response, session, stream_with_context
from services.auth_service import login_required

debate_bp = Blueprint("debate", __name__)
log = logging.getLogger("routes.debate")

_deps: dict = {}

def _init(deps: dict) -> None:
    _deps.update(deps)


@debate_bp.route("/debate", methods=["POST"])
@login_required
def debate():
    import debate as _debate
    data     = request.get_json(force=True) or {}
    question = (data.get("message") or "").strip()
    if not question:
        return jsonify({"error": "No question provided"}), 400

    asst  = _deps.get("assistant")
    token = asst.GITHUB_TOKEN if asst else ""
    model = data.get("model") or "gpt-4o-mini"

    log.info("debate: user=%s question=%r", session.get("username"), question[:60])

    def generate():
        for event in _debate.run_debate(question, token, model):
            yield "data: " + json.dumps(event) + "\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@debate_bp.route("/debate/status")
def debate_status():
    import debate as _debate
    return jsonify({"available": True, "agents": _debate.MAX_AGENTS, "personas": [p["name"] for p in _debate._PERSONAS]})
