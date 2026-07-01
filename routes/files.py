"""
routes/files.py — workspace file editor, code runner, git push
"""
import os, subprocess, logging
from flask import Blueprint, request, jsonify
from services.auth_service import login_required, current_user, no_guests, require_role

files_bp = Blueprint("files", __name__)
log = logging.getLogger("routes.files")

_deps: dict = {}

def _init(deps: dict) -> None:
    _deps.update(deps)

def _workspace_dir() -> str:
    return _deps.get("workspace_dir", "workspace")

def _asst():
    return _deps["assistant"]

_TEXT_EXTS = {
    "py","js","ts","jsx","tsx","html","css","scss","json","yaml","yml",
    "toml","ini","cfg","txt","md","rst","sh","bash","bat","ps1",
    "c","cpp","h","hpp","java","go","rs","rb","php","sql","xml","csv","env",
}
_MAX_FILE_SIZE = 2 * 1024 * 1024   # 2 MB


def _safe_path(rel: str) -> str | None:
    """Resolve rel path inside workspace; return None if path traversal."""
    ws   = _workspace_dir()
    full = os.path.normpath(os.path.join(ws, rel.lstrip("/\\")))
    return full if full.startswith(ws) else None


# ── file operations ───────────────────────────────────────────────────────────

@files_bp.route("/files/list")
@login_required
@no_guests
def files_list():
    log.debug("files_list: user=%s dir=%s", current_user(), request.args.get("dir",""))
    dir_rel = request.args.get("dir", "").strip()
    base    = _safe_path(dir_rel) if dir_rel else _workspace_dir()
    if base is None or not os.path.isdir(base):
        return jsonify({"error": "Directory not found"}), 404
    entries = []
    try:
        for name in sorted(os.listdir(base)):
            full = os.path.join(base, name)
            entries.append({
                "name":   name,
                "is_dir": os.path.isdir(full),
                "size":   0 if os.path.isdir(full) else os.path.getsize(full),
            })
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403
    return jsonify({"dir": dir_rel, "entries": entries})


@files_bp.route("/files/read")
@login_required
@no_guests
def files_read():
    rel = request.args.get("path", "").strip()
    if not rel:
        return jsonify({"error": "path required"}), 400
    full = _safe_path(rel)
    if full is None:
        return jsonify({"error": "Invalid path"}), 400
    if not os.path.isfile(full):
        return jsonify({"error": "File not found"}), 404
    ext = rel.rsplit(".", 1)[-1].lower() if "." in rel else ""
    if ext not in _TEXT_EXTS:
        return jsonify({"error": "Unsupported file type: .%s" % ext}), 415
    if os.path.getsize(full) > _MAX_FILE_SIZE:
        return jsonify({"error": "File too large (> 2 MB)"}), 413
    with open(full, "r", encoding="utf-8", errors="replace") as fh:
        return jsonify({"path": rel, "content": fh.read()})


@files_bp.route("/files/write", methods=["POST"])
@login_required
@no_guests
def files_write():
    data    = request.get_json(force=True) or {}
    rel     = (data.get("path") or "").strip()
    content = data.get("content", "")
    if not rel:
        return jsonify({"error": "path required"}), 400
    full = _safe_path(rel)
    if full is None:
        return jsonify({"error": "Invalid path"}), 400
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as fh:
        fh.write(content)
    return jsonify({"ok": True, "path": rel})


@files_bp.route("/files/delete", methods=["POST"])
@login_required
@no_guests
def files_delete():
    data = request.get_json(force=True) or {}
    rel  = (data.get("path") or "").strip()
    full = _safe_path(rel)
    if full is None:
        return jsonify({"error": "Invalid path"}), 400
    if os.path.isfile(full):
        os.unlink(full)
        return jsonify({"ok": True})
    return jsonify({"error": "File not found"}), 404


@files_bp.route("/files/mkdir", methods=["POST"])
@login_required
@no_guests
def files_mkdir():
    data = request.get_json(force=True) or {}
    rel  = (data.get("path") or "").strip()
    full = _safe_path(rel)
    if full is None:
        return jsonify({"error": "Invalid path"}), 400
    os.makedirs(full, exist_ok=True)
    return jsonify({"ok": True})


# ── code runner ───────────────────────────────────────────────────────────────

@files_bp.route("/code/run", methods=["POST"])
@login_required
@require_role("admin")
def code_run():
    log.info("code_run: user=%s", current_user())
    import tools.code_runner as _cr
    data     = request.get_json(force=True) or {}
    code     = (data.get("code") or "").strip()
    language = (data.get("language") or "python").lower()
    timeout  = str(data.get("timeout") or "30")
    stdin    = data.get("stdin", "") or ""
    ai_debug = bool(data.get("ai_debug", False))

    if not code:
        return jsonify({"error": "No code provided"}), 400

    result = _cr.run(code=code, language=language, timeout=timeout, stdin=stdin)

    if ai_debug and result.get("has_error"):
        prompt = (
            "The following %s code produced an error. "
            "Explain the bug clearly and show the corrected code.\n\n"
            "```%s\n%s\n```\n\nError:\n%s\n%s"
        ) % (language, language, code, result.get("stderr", ""),
             ("Output:\n" + result.get("stdout", "") if result.get("stdout") else ""))
        try:
            result["ai_debug"] = _asst().ask_ai_brain(prompt, with_context=False) or ""
        except Exception as ae:
            log.warning("ai_debug unavailable: %s", ae)
            result["ai_debug"] = "AI debug unavailable: %s" % ae

    return jsonify(result)


# ── git push ──────────────────────────────────────────────────────────────────

@files_bp.route("/git/push", methods=["POST"])
@login_required
@no_guests
def git_push():
    log.info("git_push: user=%s", current_user())
    data    = request.get_json(force=True) or {}
    msg     = (data.get("message") or "Update from AI Aurum").strip()
    base    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    output  = []

    def _run(cmd):
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=base, timeout=30)
        out = (r.stdout + r.stderr).strip()
        output.append(out)
        return r.returncode, out

    try:
        _run(["git", "add", "-A"])
        rc, out = _run(["git", "commit", "-m", msg])
        if rc != 0 and "nothing to commit" not in out:
            return jsonify({"ok": False, "output": "\n".join(output)})
        _run(["git", "push"])

        # Try to open GitHub Desktop
        try:
            gh_paths = [
                os.path.expandvars(r"%LOCALAPPDATA%\GitHubDesktop\GitHubDesktop.exe"),
                os.path.expandvars(r"%PROGRAMFILES%\GitHub Desktop\GitHubDesktop.exe"),
            ]
            for p in gh_paths:
                if os.path.exists(p):
                    subprocess.Popen([p])
                    break
            else:
                try:
                    os.startfile("github-windows://")
                except Exception:
                    pass
        except Exception:
            pass

        return jsonify({"ok": True, "output": "\n".join(output)})
    except Exception as e:
        log.error("git_push failed: %s", e)
        return jsonify({"ok": False, "error": str(e)}), 500


# ── git run (general) ─────────────────────────────────────────────────────────

@files_bp.route("/git/run", methods=["POST"])
@login_required
@no_guests
def git_run():
    log.info("git_run: user=%s", current_user())
    data   = request.get_json(force=True) or {}
    action = (data.get("action") or "status").strip()
    msg    = (data.get("message") or "").strip()
    custom = (data.get("custom") or "").strip()
    base   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    _SAFE = {"status", "log", "diff", "branch", "pull", "fetch", "stash",
             "commit", "push", "add", "reset"}
    if action not in _SAFE and not custom:
        return jsonify({"error": "unsafe git action"}), 400

    try:
        if custom:
            parts = custom.split()
            if parts[0] == "git":
                parts = parts[1:]
            cmd = ["git"] + parts
        elif action == "commit":
            subprocess.run(["git", "add", "-A"], cwd=base, capture_output=True, timeout=15)
            cmd = ["git", "commit", "-m", msg or "Update from AI Aurum"]
        else:
            cmd = ["git", action]

        r = subprocess.run(cmd, cwd=base, capture_output=True, text=True, timeout=30)
        output = (r.stdout + r.stderr).strip() or "(no output)"
        return jsonify({"ok": r.returncode == 0, "output": output})
    except Exception as e:
        log.error("git_run failed: %s", e)
        return jsonify({"ok": False, "error": str(e)}), 500
