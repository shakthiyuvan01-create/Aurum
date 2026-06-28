"""
routes/tools_routes.py — /tools list, run, reload, custom save; /docs; /reminders; /tts
"""
import os, re, logging
from flask import Blueprint, request, jsonify, send_from_directory, Response
from services.auth_service import login_required, current_user

tools_bp = Blueprint("tools", __name__)
log = logging.getLogger("routes.tools")

_deps: dict = {}

def _init(deps: dict) -> None:
    _deps.update(deps)

def _tools():   return _deps["tools"]
def _docs_dir() -> str:
    return _deps.get("docs_dir", "generated_docs")


# ── tool registry ─────────────────────────────────────────────────────────────

@tools_bp.route("/tools", methods=["GET"])
@login_required
def tools_list():
    return jsonify({"tools": _tools().list_tools()})


@tools_bp.route("/tools/run", methods=["POST"])
@login_required
def tools_run():
    log.info("tools_run: user=%s tool=%s", current_user(), (request.json or {}).get("tool","?"))
    body = request.json or {}
    name = body.get("tool", "").strip()
    args = body.get("args", {})
    if not name:
        return jsonify({"error": "tool name required"}), 400
    tool_info = _tools().get_tool(name)
    if tool_info and any(i["name"] == "username" for i in tool_info.get("inputs", [])):
        args.setdefault("username", current_user())
    return jsonify(_tools().call(name, **args))


@tools_bp.route("/tools/reload", methods=["POST"])
@login_required
def tools_reload():
    log.info("tools_reload: user=%s", current_user())
    _tools().reload()
    return jsonify({"ok": True, "count": len(_tools().list_tools())})


@tools_bp.route("/tools/custom/save", methods=["POST"])
@login_required
def tools_custom_save():
    body     = request.json or {}
    filename = body.get("filename", "").strip()
    code     = body.get("code", "").strip()
    if not filename or not code:
        return jsonify({"error": "filename and code required"}), 400

    safe_name = re.sub(r"[^a-zA-Z0-9_]", "_", filename.replace(".py", "")) + ".py"
    base      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    tool_path = os.path.join(base, "tools", safe_name)

    danger = ["import os", "import subprocess", "import sys", "__import__",
              "exec(", "eval(", "open(", "shutil", "socket"]
    blocked = [d for d in danger if d in code.lower()]
    if blocked:
        return jsonify({"error": "Custom tools cannot use: %s" % ", ".join(blocked)}), 400

    try:
        with open(tool_path, "w", encoding="utf-8") as f:
            f.write(code)
        _tools().reload()
        return jsonify({"ok": True, "filename": safe_name,
                        "message": "Tool saved as '%s' and loaded." % safe_name})
    except Exception as e:
        log.error("custom tool save failed: %s", e)
        return jsonify({"error": str(e)}), 500


# ── generated documents ───────────────────────────────────────────────────────

@tools_bp.route("/docs/<path:filename>")
@login_required
def serve_doc(filename):
    if re.search(r"[/\\\.]{2,}|^\.", filename):
        return jsonify({"error": "invalid filename"}), 400
    return send_from_directory(_docs_dir(), filename, as_attachment=True)


# ── reminders ─────────────────────────────────────────────────────────────────

@tools_bp.route("/reminders/due", methods=["GET"])
def reminders_due():
    uname = current_user()
    if not uname:
        return jsonify({"reminders": []})
    try:
        from tools.reminders import get_due_reminders
        return jsonify({"reminders": get_due_reminders(uname)})
    except Exception as e:
        log.warning("reminders_due error: %s", e)
        return jsonify({"reminders": []})


# ── TTS (ElevenLabs) ──────────────────────────────────────────────────────────

@tools_bp.route("/tts", methods=["POST"])
def tts_route():
    text = (request.json or {}).get("text", "").strip()
    if not text:
        return jsonify({"error": "no text"}), 400

    key      = os.getenv("ELEVENLABS_API_KEY", "")
    voice_id = os.getenv("ELEVENLABS_VOICE_ID", "EXAVITQu4vr4xnSDxMaL")
    if not key:
        return jsonify({"error": "no ELEVENLABS_API_KEY"}), 400

    try:
        import requests as _req
        r = _req.post(
            "https://api.elevenlabs.io/v1/text-to-speech/%s" % voice_id,
            headers={"xi-api-key": key, "Content-Type": "application/json"},
            json={"text": text, "model_id": "eleven_multilingual_v2",
                  "voice_settings": {"stability": 0.5, "similarity_boost": 0.8}},
            timeout=30,
        )
        if r.status_code == 200:
            return Response(r.content, mimetype="audio/mpeg")
        return jsonify({"error": "ElevenLabs %d" % r.status_code}), 500
    except Exception as e:
        log.error("tts_route failed: %s", e)
        return jsonify({"error": str(e)}), 500
