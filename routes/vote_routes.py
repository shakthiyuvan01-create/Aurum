"""routes/vote_routes.py — Model voting API."""
import json, logging
from flask import Blueprint, request, jsonify, Response, session, stream_with_context
from services.auth_service import login_required

vote_bp = Blueprint("vote", __name__)
log = logging.getLogger("routes.vote")

_deps: dict = {}
def _init(deps): _deps.update(deps)


@vote_bp.route("/vote", methods=["POST"])
@login_required
def vote():
    data     = request.get_json(force=True) or {}
    question = (data.get("message") or data.get("question") or "").strip()
    if not question:
        return jsonify({"error": "question required"}), 400
    from services.model_voting import vote_stream

    def generate():
        for event in vote_stream(question, data.get("system","")):
            yield "data: " + json.dumps(event) + "\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"},
    )
