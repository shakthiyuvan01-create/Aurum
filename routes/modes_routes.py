"""Web routes for the 6 Modes system."""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request, render_template_string

from modes import modes, ModeType

logger = logging.getLogger(__name__)

modes_bp = Blueprint("modes", __name__, url_prefix="/api/modes")


@modes_bp.route("", methods=["GET"])
def list_modes():
    """List all six modes with their capabilities."""
    return jsonify({
        "success": True,
        "modes": [
            {
                "type": m.type.value,
                "name": m.name,
                "description": m.description,
                "icon": m.icon,
                "capabilities": m.capabilities,
            }
            for m in modes.all_modes
        ],
    })


@modes_bp.route("/<mode_type>", methods=["GET"])
def get_mode(mode_type: str):
    """Get details and status of a specific mode."""
    try:
        mt = ModeType(mode_type)
    except ValueError:
        return jsonify({"success": False, "error": f"Unknown mode: {mode_type}"}), 400

    mode_handler = modes.get_mode(mt)
    if not mode_handler:
        return jsonify({"success": False, "error": "Mode handler not found"}), 500

    status = {}
    try:
        status = mode_handler.status()
    except Exception:
        status = {}

    return jsonify({
        "success": True,
        "mode": {
            "type": mt.value,
            "name": mode_handler.name,
            "icon": mode_handler.icon,
            "capabilities": mode_handler.get_capabilities(),
        },
        "status": status,
    })


@modes_bp.route("/status", methods=["GET"])
def all_status():
    """Get status of all modes."""
    return jsonify({"success": True, "status": modes.status_report()})


# ---------------------------------------------------------------------------
# Mode-specific endpoints
# ---------------------------------------------------------------------------

@modes_bp.route("/memory/fact", methods=["POST"])
def remember_fact():
    data = request.get_json(force=True) or {}
    fact = data.get("fact", "").strip()
    if not fact:
        return jsonify({"success": False, "error": "Fact is required"}), 400
    ok = modes.memory.remember_fact(fact, data.get("username", "default"))
    return jsonify({"success": ok})


@modes_bp.route("/memory/recall", methods=["POST"])
def recall():
    data = request.get_json(force=True) or {}
    query = data.get("query", "").strip()
    if not query:
        return jsonify({"success": False, "error": "Query is required"}), 400
    results = modes.memory.recall(query, data.get("username", "default"))
    return jsonify({"success": True, "results": results})


@modes_bp.route("/memory/preferences", methods=["GET"])
def get_preferences():
    username = request.args.get("username", "default")
    prefs = modes.memory.get_preferences(username)
    return jsonify({"success": True, "preferences": prefs})


@modes_bp.route("/memory/preferences", methods=["POST"])
def set_preference():
    data = request.get_json(force=True) or {}
    key, value = data.get("key"), data.get("value")
    if not key or value is None:
        return jsonify({"success": False, "error": "key and value required"}), 400
    ok = modes.memory.save_preference(key, value, data.get("username", "default"))
    return jsonify({"success": ok})


@modes_bp.route("/voice/say", methods=["POST"])
def speak():
    data = request.get_json(force=True) or {}
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"success": False, "error": "Text is required"}), 400
    ok = modes.voice.say(text)
    return jsonify({"success": ok, "text": text})


@modes_bp.route("/workflow/list", methods=["GET"])
def list_workflows():
    username = request.args.get("username", "default")
    wfs = modes.workflow.list_workflows(username)
    return jsonify({"success": True, "workflows": wfs})


@modes_bp.route("/workflow/run", methods=["POST"])
def run_workflow():
    data = request.get_json(force=True) or {}
    wf_id = data.get("id", "")
    username = data.get("username", "default")
    result = modes.workflow.run_workflow(wf_id, username)
    return jsonify(result)


@modes_bp.route("/workflow/schedule", methods=["POST"])
def schedule():
    data = request.get_json(force=True) or {}
    name = data.get("name", "task")
    task_type = data.get("type", "log")
    params = data.get("params", {})
    interval = data.get("interval_minutes")
    delay = data.get("delay_minutes", 0)
    job_id = modes.workflow.schedule_task(name, task_type, params, interval, delay)
    if job_id:
        return jsonify({"success": True, "job_id": job_id})
    return jsonify({"success": False, "error": "Failed to schedule"}), 500


@modes_bp.route("/developer/code/run", methods=["POST"])
def run_code():
    data = request.get_json(force=True) or {}
    code = data.get("code", "").strip()
    language = data.get("language", "python")
    if not code:
        return jsonify({"success": False, "error": "Code is required"}), 400
    result = modes.developer.run_code(code, language)
    return jsonify(result)


@modes_bp.route("/developer/code/generate", methods=["POST"])
def generate_code():
    data = request.get_json(force=True) or {}
    task = data.get("task", "").strip()
    language = data.get("language", "python")
    if not task:
        return jsonify({"success": False, "error": "Task is required"}), 400
    result = modes.developer.generate_code(task, language)
    return jsonify({"success": True, "code": result})


@modes_bp.route("/creator/image/generate", methods=["POST"])
def create_image():
    data = request.get_json(force=True) or {}
    prompt = data.get("prompt", "").strip()
    if not prompt:
        return jsonify({"success": False, "error": "Prompt is required"}), 400
    path = modes.creator.generate_image(prompt, data.get("provider"), data.get("aspect_ratio", "square"))
    return jsonify({"success": bool(path), "image": path})


@modes_bp.route("/creator/brainstorm", methods=["POST"])
def brainstorm():
    data = request.get_json(force=True) or {}
    topic = data.get("topic", "").strip()
    if not topic:
        return jsonify({"success": False, "error": "Topic is required"}), 400
    ideas = modes.creator.brainstorm(topic, data.get("count", 5))
    return jsonify({"success": True, "ideas": ideas})


@modes_bp.route("/security/2fa/enroll", methods=["POST"])
def enroll_2fa():
    data = request.get_json(force=True) or {}
    username = data.get("username", "default")
    result = modes.security.enroll_2fa(username)
    if result:
        return jsonify({"success": True, "setup": result})
    return jsonify({"success": False, "error": "2FA enrollment failed"}), 500


@modes_bp.route("/security/2fa/verify", methods=["POST"])
def verify_2fa():
    data = request.get_json(force=True) or {}
    secret = data.get("secret", "")
    code = data.get("code", "")
    ok = modes.security.verify_2fa(secret, code)
    return jsonify({"success": ok})
