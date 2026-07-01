"""
routes/tools_routes.py — /tools list, run, reload, custom save; /docs; /reminders; /tts
"""
import ast, os, re, logging
from flask import Blueprint, request, jsonify, send_from_directory, Response
import uuid
from services.auth_service import login_required, current_user, no_guests

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

    # AST-based security check — blocklists are trivially bypassed via encoding tricks
    try:
        tree = ast.parse(code)
    except SyntaxError as se:
        return jsonify({"error": "Syntax error: %s" % se}), 400

    _BLOCKED_MODULES = {"os", "sys", "subprocess", "shutil", "socket", "importlib",
                        "ctypes", "builtins", "pathlib", "tempfile", "pty", "signal"}
    _BLOCKED_CALLS   = {"eval", "exec", "compile", "open", "__import__", "getattr",
                        "setattr", "delattr", "vars", "globals", "locals", "dir"}

    class _SecVisitor(ast.NodeVisitor):
        def __init__(self):
            self.violations = []
        def visit_Import(self, node):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in _BLOCKED_MODULES:
                    self.violations.append("import %s" % alias.name)
            self.generic_visit(node)
        def visit_ImportFrom(self, node):
            root = (node.module or "").split(".")[0]
            if root in _BLOCKED_MODULES:
                self.violations.append("from %s import ..." % node.module)
            self.generic_visit(node)
        def visit_Call(self, node):
            name = ""
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                name = node.func.attr
            if name in _BLOCKED_CALLS:
                self.violations.append("%s()" % name)
            self.generic_visit(node)

    visitor = _SecVisitor()
    visitor.visit(tree)
    if visitor.violations:
        return jsonify({"error": "Blocked constructs: %s" % ", ".join(visitor.violations)}), 400

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


# ── Skills (Self-Evolving) ────────────────────────────────────────────────────

def _db():
    return _deps.get("db")


@tools_bp.route("/skills", methods=["GET"])
@login_required
@no_guests
def skills_list():
    uname = current_user()
    db = _db()
    if db is None:
        return jsonify({"error": "db not available"}), 500
    return jsonify({"skills": db.get_skills(uname)})


@tools_bp.route("/skills", methods=["POST"])
@login_required
@no_guests
def skills_save():
    uname = current_user()
    db = _db()
    body = request.get_json(force=True) or {}
    name        = (body.get("name") or "").strip()
    description = (body.get("description") or "").strip()
    content     = (body.get("content") or "").strip()
    tags        = body.get("tags") or []
    skill_id    = body.get("id") or str(uuid.uuid4())[:8]

    if not name or not content:
        return jsonify({"error": "name and content are required"}), 400

    db.save_skill(uname, skill_id, name, description, content,
                  tags if isinstance(tags, list) else [t.strip() for t in str(tags).split(",")])
    log.info("skill saved: %s by %s", name, uname)
    return jsonify({"ok": True, "id": skill_id, "name": name})


@tools_bp.route("/skills/<skill_id>", methods=["DELETE"])
@login_required
@no_guests
def skills_delete(skill_id):
    uname = current_user()
    _db().delete_skill(skill_id, uname)
    return jsonify({"ok": True})


@tools_bp.route("/skills/search")
@login_required
@no_guests
def skills_search():
    uname = current_user()
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"skills": []})
    return jsonify({"skills": _db().search_skills(uname, query)})


# ── Project Context ───────────────────────────────────────────────────────────

@tools_bp.route("/project", methods=["GET"])
@login_required
def project_get():
    return jsonify(_db().get_project_context(current_user()))


@tools_bp.route("/project", methods=["POST"])
@login_required
@no_guests
def project_save():
    uname = current_user()
    body  = request.get_json(force=True) or {}
    _db().save_project_context(
        username    = uname,
        name        = (body.get("name") or "").strip(),
        description = (body.get("description") or "").strip(),
        tech_stack  = body.get("tech_stack") or [],
        goals       = (body.get("goals") or "").strip(),
        env_info    = body.get("env_info") or {},
    )
    log.info("project context updated for %s", uname)
    return jsonify({"ok": True})
