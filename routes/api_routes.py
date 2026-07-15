"""
routes/api_routes.py -- machine API for external apps.

Auth: X-API-Key header must match AURUM_API_KEY env (set a long random value).
  POST /api/ask        {"message": "...")   -> {"reply": ...}
  POST /api/team       {"goal": "..."}      -> full team run
  POST /api/tool       {"tool": ..., "args": {}} -> any registered tool
  POST /api/webhook/<name>                  -> fires event bus + optional mission
"""
import os
import logging
from functools import wraps
from flask import Blueprint, request, jsonify

api_bp = Blueprint("api", __name__)
log = logging.getLogger("routes.api")

_deps: dict = {}

def _init(deps: dict) -> None:
    _deps.update(deps)


def require_api_key(f):
    @wraps(f)
    def _wrap(*a, **kw):
        key = os.getenv("AURUM_API_KEY", "")
        if not key:
            return jsonify({"error": "API disabled: set AURUM_API_KEY in .env"}), 503
        if request.headers.get("X-API-Key", "") != key:
            return jsonify({"error": "invalid API key"}), 401
        return f(*a, **kw)
    return _wrap


@api_bp.route("/api/ask", methods=["POST"])
@require_api_key
def api_ask():
    b = request.get_json(force=True) or {}
    msg = (b.get("message") or "").strip()
    if not msg:
        return jsonify({"error": "message required"}), 400
    from providers import AI
    reply = AI.generate(msg, system=b.get("system", ""),
                        max_tokens=int(b.get("max_tokens", 1200)))
    return jsonify({"reply": reply, "provider": AI.last_used})


@api_bp.route("/api/team", methods=["POST"])
@require_api_key
def api_team():
    b = request.get_json(force=True) or {}
    goal = (b.get("goal") or "").strip()
    if not goal:
        return jsonify({"error": "goal required"}), 400
    import agents
    return jsonify(agents.run_team(goal, username=b.get("username", "api")))


@api_bp.route("/api/tool", methods=["POST"])
@require_api_key
def api_tool():
    b = request.get_json(force=True) or {}
    name = (b.get("tool") or "").strip()
    if not name:
        return jsonify({"error": "tool required"}), 400
    import tools as _tools
    return jsonify(_tools.call(name, **(b.get("args") or {})))


@api_bp.route("/api/webhook/<name>", methods=["POST"])
@require_api_key
def api_webhook(name):
    payload = request.get_json(silent=True) or {}
    try:
        from services.event_bus import bus
        bus.emit("webhook." + name, payload, async_=True)
    except Exception:
        pass
    log.info("webhook fired: %s", name)
    return jsonify({"ok": True, "event": "webhook." + name})


@api_bp.route("/slack/events", methods=["POST"])
def slack_events():
    """Slack Event Subscriptions endpoint (set this URL in your Slack app)."""
    import os as _os
    body = request.get_json(silent=True) or {}
    # URL verification handshake
    if body.get("type") == "url_verification":
        return jsonify({"challenge": body.get("challenge", "")})
    ev = body.get("event", {})
    if ev.get("type") == "message" and not ev.get("bot_id"):
        text = (ev.get("text") or "").strip()
        chan = ev.get("channel")
        if text and chan:
            try:
                from services.slack_bot import answer, send
                send(chan, answer(text, _os.getenv("SLACK_USER", "default")))
            except Exception as e:
                log.warning("slack handle: %s", e)
    return jsonify({"ok": True})
