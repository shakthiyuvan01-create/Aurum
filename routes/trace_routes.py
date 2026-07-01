"""routes/trace_routes.py — Observability / tracing API."""
import json, logging
from flask import Blueprint, jsonify, request, session
from services.auth_service import login_required

trace_bp = Blueprint("traces", __name__)
log = logging.getLogger("routes.traces")

_deps: dict = {}
def _init(deps): _deps.update(deps)


@trace_bp.route("/traces")
@login_required
def list_traces():
    from services.tracer import tracer
    username = session.get("username", "guest")
    limit    = int(request.args.get("limit", 20))
    return jsonify({"traces": tracer.list_traces(username, limit)})


@trace_bp.route("/traces/<trace_id>")
@login_required
def get_trace(trace_id: str):
    from services.tracer import tracer
    trace = tracer.get_trace(trace_id)
    if not trace:
        return jsonify({"error": "Not found"}), 404
    return jsonify(trace)


@trace_bp.route("/traces/<trace_id>/graph")
@login_required
def get_trace_graph(trace_id: str):
    from services.tracer import tracer
    return jsonify(tracer.build_graph(trace_id))
