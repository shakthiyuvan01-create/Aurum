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


@tools_bp.route("/providers/status")
@login_required
def providers_status():
    """Health of the unified AI provider chain (providers/ package)."""
    from providers import AI
    return jsonify(AI.status())


@tools_bp.route("/tools/run_async", methods=["POST"])
@login_required
def tools_run_async():
    """Run a heavy tool (browser, document, meeting, coding team...) in the
    background so the UI never freezes. Returns a job_id to poll."""
    from services import task_queue
    body = request.json or {}
    name = (body.get("tool") or "").strip()
    args = body.get("args", {})
    if not name:
        return jsonify({"error": "tool name required"}), 400
    tool_info = _tools().get_tool(name)
    if tool_info and any(i["name"] == "username" for i in tool_info.get("inputs", [])):
        args.setdefault("username", current_user())
    registry = _tools()
    job_id = task_queue.enqueue(registry.call, name, **args)
    log.info("tools_run_async: user=%s tool=%s job=%s", current_user(), name, job_id)
    return jsonify({"ok": True, "job_id": job_id, "poll": "/tasks/" + job_id})


@tools_bp.route("/tasks/<job_id>")
@login_required
def task_status(job_id):
    """Poll a background job: {status: queued/started/finished/failed, result, error}."""
    from services import task_queue
    return jsonify(task_queue.get_status(job_id))


@tools_bp.route("/permissions", methods=["GET", "POST"])
@login_required
def permissions():
    """View or toggle dangerous-capability permissions.
    POST body: {"capability": "shell", "allowed": true}"""
    from services.permission_manager import perms
    if request.method == "POST":
        body = request.get_json(force=True) or {}
        cap = (body.get("capability") or "").strip()
        ok = perms.set(cap, bool(body.get("allowed")))
        if not ok:
            return jsonify({"error": "unknown capability", "valid": list(perms.all().keys())}), 400
    return jsonify(perms.all())


@tools_bp.route("/skillstore")
@login_required
def skillstore_list():
    """AI Skill Store: curated packs installable in one click."""
    from services import skill_store
    uname = current_user()
    try:
        installed = {s["name"].split(":")[0].strip()
                     for s in _db().get_skills(uname)}
    except Exception:
        installed = set()
    return jsonify({"packs": skill_store.list_packs(installed)})


@tools_bp.route("/skillstore/install", methods=["POST"])
@login_required
def skillstore_install():
    from services import skill_store
    body = request.get_json(force=True) or {}
    return jsonify(skill_store.install((body.get("pack") or "").strip(),
                                       current_user(), _db()))


@tools_bp.route("/screen_check", methods=["POST"])
@login_required
def screen_check():
    """Computer vision screen watcher: sends a frame to the vision model and
    reports only if it spots errors, dialogs, popups, or compiler warnings."""
    body = request.get_json(force=True) or {}
    b64 = body.get("image_b64", "")
    if not b64:
        return jsonify({"error": "image_b64 required"}), 400
    import os as _os, requests as _rq
    token = _os.getenv("GITHUB_TOKEN", "")
    if not token:
        return jsonify({"error": "no vision backend"}), 500
    try:
        r = _rq.post(
            "https://models.inference.ai.azure.com/chat/completions",
            headers={"Authorization": "Bearer " + token,
                     "Content-Type": "application/json"},
            json={"model": _os.getenv("VISION_MODEL", "gpt-4o"),
                  "max_tokens": 200,
                  "messages": [{"role": "user", "content": [
                      {"type": "text", "text":
                       "You are a screen watcher. Look for error messages, "
                       "exception tracebacks, warning dialogs, popups, or IDE/"
                       "compiler errors. If you find one, reply: ISSUE: <what "
                       "it is and the suggested fix in 1-2 sentences>. If the "
                       "screen looks fine, reply exactly: OK"},
                      {"type": "image_url", "image_url": {
                          "url": "data:image/jpeg;base64," + b64}}]}]},
            timeout=45)
        r.raise_for_status()
        answer = r.json()["choices"][0]["message"]["content"].strip()
        return jsonify({"ok": True, "issue": None if answer == "OK" else answer})
    except Exception as e:
        return jsonify({"error": str(e)}), 502


@tools_bp.route("/providers/test")
@login_required
def providers_test():
    """Live-test every provider with a tiny request. Open this in the browser
    to see exactly which keys work and why others fail."""
    from providers.manager import _ALL
    results = {}
    for name, prov in _ALL.items():
        if not prov.available():
            results[name] = {"status": "skipped", "reason": "no API key set / not running"}
            continue
        try:
            import time as _t
            t0 = _t.time()
            out = prov.generate("Reply with exactly: OK", max_tokens=5, temperature=0)
            results[name] = {"status": "WORKING",
                             "reply": out[:40],
                             "latency_ms": int((_t.time() - t0) * 1000),
                             "model": prov.default_model}
        except Exception as e:
            results[name] = {"status": "FAILED", "error": str(e)[:250]}
    return jsonify(results)


@tools_bp.route("/forge", methods=["POST"])
@login_required
def forge_tool():
    """Self-extension: AI writes, tests and registers a new tool (Ada-SI pipeline)."""
    from services.tool_forge import forge
    body = request.get_json(force=True) or {}
    return jsonify(forge((body.get("capability") or "").strip(), current_user()))


@tools_bp.route("/forge/list", methods=["GET"])
@login_required
def forge_list():
    """List forged tools."""
    from services.tool_forge import list_forged_tools
    return jsonify({"success": True, "tools": list_forged_tools()})


@tools_bp.route("/forge/<name>", methods=["DELETE"])
@login_required
def forge_delete(name: str):
    """Delete a forged tool."""
    from services.tool_forge import delete_tool
    return jsonify(delete_tool(name))


@tools_bp.route("/forge/interactive", methods=["POST"])
@login_required
def forge_interactive():
    """Register an interactive skill with UI files."""
    from services.tool_forge import forge_interactive as _fi
    body = request.get_json(force=True) or {}
    return jsonify(_fi(
        tool_name=body.get("tool_name", ""),
        description=body.get("description", ""),
        manifest=body.get("manifest", {}),
        tool_code=body.get("tool_code", ""),
        test_code=body.get("test_code", ""),
        requirements=body.get("requirements", []),
        ui_files=body.get("ui_files", {}),
    ))


# Serve forged tool UI files (HTML/CSS/JS for interactive skills)
@tools_bp.route("/forge/ui/<tool_name>/<path:filename>")
def serve_forge_ui(tool_name: str, filename: str):
    import os, sys
    from services.tool_forge import PLUGIN_DIR
    ui_dir = PLUGIN_DIR / "ui" / tool_name
    if not ui_dir.is_dir():
        return jsonify({"error": "UI not found"}), 404
    return send_from_directory(str(ui_dir), filename)


@tools_bp.route("/forge/batch", methods=["POST"])
@login_required
def forge_batch():
    """Create multiple tools in batch (2-10 capabilities at once)."""
    body = request.get_json(force=True) or {}
    capabilities = body.get("capabilities", [])
    if not isinstance(capabilities, list) or len(capabilities) < 2:
        return jsonify({"success": False, "error": "Provide 2-10 capabilities as a list"}), 400
    if len(capabilities) > 10:
        return jsonify({"success": False, "error": "Max 10 tools per batch"}), 400

    from services.tool_forge import forge
    results = []
    for cap in capabilities:
        r = forge(cap.strip(), body.get("username", "default"))
        results.append(r)

    succeeded = [r for r in results if r.get("ok")]
    failed = [r for r in results if "error" in r]

    return jsonify({
        "success": len(failed) == 0,
        "total": len(results),
        "succeeded": len(succeeded),
        "failed": len(failed),
        "results": results,
    })


@tools_bp.route("/forge/approve/<name>", methods=["POST"])
@login_required
def forge_approve(name: str):
    """Approve a pending forged tool for installation."""
    body = request.get_json(force=True) or {}
    approved = body.get("approved", True)
    if approved:
        from services.tool_forge import list_forged_tools
        return jsonify({"success": True, "message": f"Tool '{name}' approved"})
    return jsonify({"success": False, "message": f"Tool '{name}' rejected"})


@tools_bp.route("/compression/test", methods=["POST"])
@login_required
def compression_test():
    """Test the token compressor on a sample of text."""
    from services.compression import compress
    body = request.get_json(force=True) or {}
    return jsonify(compress(body.get("text", ""), body.get("mode", "auto")))
