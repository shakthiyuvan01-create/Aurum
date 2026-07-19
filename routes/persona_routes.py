"""Web routes for the Persona system (Ada-SI pattern).

Persona file management, daily logs, bootstrap ritual, and tool-call handlers
for soul_replace / persona_replace / memory_replace / daily_log_append / bootstrap_complete.
"""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request

from services.persona import (
    bootstrap_complete,
    bootstrap_exists,
    bootstrap_path,
    daily_logs_dir,
    ensure_persona_layout,
    get_heartbeat_state,
    list_files,
    load_persona_config,
    read,
    save_persona_config,
    set_heartbeat_state,
    system_block,
    tail_recent_daily_logs,
    write,
    PERSONA_TOOL_DECLARATIONS,
    PERSONA_TOOL_HANDLERS,
)

logger = logging.getLogger(__name__)

persona_bp = Blueprint("persona", __name__, url_prefix="/api/persona")


@persona_bp.route("", methods=["GET"])
def get_persona_index():
    """List all persona files with metadata."""
    return jsonify({
        "success": True,
        "files": list_files(),
        "bootstrap_active": bootstrap_exists(),
        "config": load_persona_config(),
    })


@persona_bp.route("/<name>", methods=["GET"])
def get_persona_file(name: str):
    """Read a persona markdown file."""
    content = read(name)
    if content == "":
        from pathlib import Path
        base = bootstrap_path().parent
        found = list(base.glob(f"{name.upper()}.md")) + list(base.glob(f"{name}.md"))
        if not found:
            return jsonify({"success": False, "error": f"Unknown persona file: {name}"}), 404
    return jsonify({
        "success": True,
        "name": name.upper(),
        "content": content,
    })


@persona_bp.route("/<name>", methods=["POST"])
def set_persona_file(name: str):
    """Write a persona markdown file."""
    data = request.get_json(force=True) or {}
    content = data.get("content", "")
    by_ai = data.get("by_ai", False)
    result = write(name, content, by_ai=by_ai)
    if "error" in result:
        return jsonify({"success": False, **result}), 400
    return jsonify({"success": True, **result})


@persona_bp.route("/system-block", methods=["GET"])
def get_system_block():
    """Get the persona block injected into system prompts."""
    return jsonify({
        "success": True,
        "system_block": system_block(),
    })


# -- Daily logs -----------------------------------------------------------------


@persona_bp.route("/logs", methods=["GET"])
def get_daily_logs():
    """List daily log files."""
    ensure_persona_layout()
    logs = sorted(
        daily_logs_dir().glob("????-??-??.md"),
        reverse=True,
    )
    return jsonify({
        "success": True,
        "logs": [
            {
                "date": p.stem,
                "size": p.stat().st_size,
            }
            for p in logs[:30]
        ],
    })


@persona_bp.route("/logs/<date>", methods=["GET"])
def get_daily_log_route(date: str):
    """Read a specific daily log file."""
    path = daily_logs_dir() / f"{date}.md"
    if not path.is_file():
        return jsonify({"success": False, "error": "Log not found"}), 404
    return jsonify({
        "success": True,
        "date": date,
        "content": path.read_text(encoding="utf-8"),
    })


@persona_bp.route("/logs/tail", methods=["GET"])
def get_logs_tail():
    """Get tail of recent daily logs (for heartbeat / context injection)."""
    days = request.args.get("days", 7, type=int)
    return jsonify({
        "success": True,
        "content": tail_recent_daily_logs(days=days),
    })


@persona_bp.route("/logs/append", methods=["POST"])
def append_log():
    """Append a line to today's daily log."""
    data = request.get_json(force=True) or {}
    line = data.get("line", "")
    if not line.strip():
        return jsonify({"success": False, "error": "Line is required"}), 400
    from services.persona import append_daily_log
    result = append_daily_log(line)
    if not result.get("ok"):
        return jsonify({"success": False, **result}), 500
    return jsonify({"success": True, **result})


# -- Bootstrap ------------------------------------------------------------------


@persona_bp.route("/bootstrap", methods=["GET"])
def get_bootstrap():
    """Check if bootstrap ritual is active."""
    return jsonify({
        "success": True,
        "active": bootstrap_exists(),
    })


@persona_bp.route("/bootstrap/complete", methods=["POST"])
def complete_bootstrap():
    """Complete the bootstrap ritual (delete BOOTSTRAP.md)."""
    result = bootstrap_complete()
    if not result.get("ok"):
        return jsonify({"success": False, **result}), 500
    return jsonify({"success": True, **result})


# -- Config ---------------------------------------------------------------------


@persona_bp.route("/config", methods=["GET"])
def get_config():
    """Get persona config (heartbeat settings, etc.)."""
    return jsonify({
        "success": True,
        "config": load_persona_config(),
    })


@persona_bp.route("/config", methods=["POST"])
def update_config():
    """Update persona config."""
    data = request.get_json(force=True) or {}
    config = save_persona_config(data)
    return jsonify({"success": True, "config": config})


# -- Heartbeat state ------------------------------------------------------------


@persona_bp.route("/heartbeat-state", methods=["GET"])
def get_hb_state():
    """Get heartbeat state (last run, etc.)."""
    return jsonify({
        "success": True,
        "state": get_heartbeat_state(),
    })


# -- Tool-call handlers (for AI function calling) --------------------------------


@persona_bp.route("/tools", methods=["GET"])
def get_persona_tools():
    """Get the persona tool declarations (for AI function calling)."""
    return jsonify({
        "success": True,
        "tools": PERSONA_TOOL_DECLARATIONS,
    })


@persona_bp.route("/tools/run", methods=["POST"])
def run_persona_tool():
    """Run a persona tool by name with arguments."""
    data = request.get_json(force=True) or {}
    tool_name = data.get("tool", "")
    args = data.get("arguments", {})

    if tool_name not in PERSONA_TOOL_HANDLERS:
        return jsonify({
            "success": False,
            "error": f"Unknown persona tool: {tool_name}",
        }), 400

    try:
        result = PERSONA_TOOL_HANDLERS[tool_name](args)
        return jsonify({"success": True, "result": result})
    except Exception as e:
        logger.exception("persona tool %s failed", tool_name)
        return jsonify({"success": False, "error": str(e)}), 500
