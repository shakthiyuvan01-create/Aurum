"""routes/agents_routes.py — Multi-agent team API endpoints."""
import json, logging, time
from flask import Blueprint, request, jsonify, Response, session, stream_with_context
from services.auth_service import login_required

agents_bp = Blueprint("agents", __name__)
log = logging.getLogger("routes.agents")

_deps: dict = {}

def _init(deps: dict) -> None:
    _deps.update(deps)


@agents_bp.route("/agents")
@login_required
def list_agents():
    import agents as _agents
    return jsonify({"agents": _agents.list_agents()})


@agents_bp.route("/agents/run", methods=["POST"])
@login_required
def run_team():
    """Run full CEO-orchestrated multi-agent team on a goal. SSE stream."""
    data     = request.get_json(force=True) or {}
    goal     = (data.get("goal") or data.get("message") or "").strip()
    username = session.get("username", "guest")
    if not goal:
        return jsonify({"error": "goal required"}), 400

    import agents as _agents

    def generate():
        try:
            for event in _agents.run_team_stream(goal, username=username):
                if event.get("done"):
                    # Stream final reply word by word, then the done payload
                    yield "data: " + json.dumps({"synthesising": True}) + "\n\n"
                    for word in event["reply"].split():
                        yield "data: " + json.dumps({"delta": word + " "}) + "\n\n"
                    yield "data: " + json.dumps({
                        "done":     True,
                        "reply":    event["reply"],
                        "plan":     event["plan"],
                        "duration": event["duration"],
                    }) + "\n\n"
                else:
                    yield "data: " + json.dumps(event) + "\n\n"
        except Exception as e:
            log.error("run_team error: %s", e)
            yield "data: " + json.dumps({"error": str(e)}) + "\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@agents_bp.route("/agents/<agent_name>/ask", methods=["POST"])
@login_required
def ask_agent(agent_name: str):
    """Ask a specific specialist agent directly."""
    import agents as _agents
    data     = request.get_json(force=True) or {}
    task     = (data.get("task") or data.get("message") or "").strip()
    username = session.get("username", "guest")
    if not task:
        return jsonify({"error": "task required"}), 400
    agent  = _agents.get_agent(agent_name, username)
    result = agent.think(task, context=data.get("context", ""))
    return jsonify({"agent": agent_name, "result": result})


@agents_bp.route("/agents/health")
@login_required
def agents_health():
    """Return health scores for all registered agents."""
    from services.agent_health import health
    from services.capability_registry import registry
    out = {}
    for name in registry._agents:
        stats = health.stats(name)
        out[name] = {
            "score":        round(health.score(name), 3),
            "is_healthy":   health.score(name) >= 0.40,
            "call_count":   stats.call_count,
            "success_rate": round(stats.success_count / max(stats.call_count, 1), 3),
            "avg_latency_ms": round(stats.avg_latency_ms, 1),
        }
    return __import__("flask").jsonify({"agents": out})


@agents_bp.route("/agents/best", methods=["POST"])
@login_required
def best_agent():
    """Return the best agent for a given task (registry + health scoring)."""
    data = __import__("flask").request.get_json(force=True) or {}
    task = (data.get("task") or "").strip()
    if not task:
        return __import__("flask").jsonify({"error": "task required"}), 400
    from services.capability_registry import registry
    from services.agent_health import health
    ranked = registry.rank(task, top_n=5)
    candidates = [name for name, _ in ranked]
    best = health.pick_healthy(candidates) if candidates else "researcher"
    return __import__("flask").jsonify({
        "best":    best,
        "ranked":  [{"agent": n, "score": round(s, 3)} for n, s in ranked],
    })


@agents_bp.route("/history")
@login_required
def task_history():
    """Task history: team runs, background jobs (newest first)."""
    from services import activity_log
    username = session.get("username", "guest")
    return jsonify({"history": activity_log.get_history(
        username, limit=int(request.args.get("limit", 50)))})


@agents_bp.route("/agents/logs")
@login_required
def agent_logs():
    """Persisted agent event logs (from the event bus)."""
    from services import activity_log
    username = session.get("username", "guest")
    return jsonify({"logs": activity_log.get_logs(
        username=username,
        limit=int(request.args.get("limit", 100)),
        event_prefix=request.args.get("event", ""))})
