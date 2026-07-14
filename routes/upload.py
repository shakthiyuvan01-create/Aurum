"""
routes/upload.py — image upload, file serving, screenshot
"""
import os, uuid, re, time, base64, logging
from flask import Blueprint, request, jsonify, send_from_directory
from services.auth_service import login_required, current_user, no_guests

upload_bp = Blueprint("upload", __name__)
log = logging.getLogger("routes.upload")

_deps: dict = {}

def _init(deps: dict) -> None:
    _deps.update(deps)

def _upload_dir() -> str:
    return _deps.get("upload_dir", "uploads")

def _static_dir() -> str:
    return _deps.get("static_dir", "static")

MIME_MAP = {
    "jpg":  "image/jpeg",
    "jpeg": "image/jpeg",
    "png":  "image/png",
    "gif":  "image/gif",
    "webp": "image/webp",
}


@upload_bp.route("/static/<path:filename>")
def serve_static(filename):
    return send_from_directory(_static_dir(), filename)


@upload_bp.route("/upload/image", methods=["POST"])
@login_required
@no_guests
def upload_image():
    log.info("upload_image: user=%s", current_user())
    f = request.files.get("image")
    if not f:
        return jsonify({"error": "No file"}), 400
    ext  = os.path.splitext(f.filename)[1].lower() or ".jpg"
    name = uuid.uuid4().hex + ext
    path = os.path.join(_upload_dir(), name)
    f.save(path)
    mime = MIME_MAP.get(ext.lstrip("."), "image/jpeg")
    with open(path, "rb") as fh:
        b64 = base64.b64encode(fh.read()).decode()
    return jsonify({"ok": True, "filename": name,
                    "b64": b64, "mime": mime,
                    "url": "/uploads/%s" % name})


@upload_bp.route("/upload/file", methods=["POST"])
@login_required
@no_guests
def upload_file():
    """Generic file upload (video/audio/docs) for tools. Returns server path."""
    f = request.files.get("file")
    if not f:
        return jsonify({"error": "No file"}), 400
    ext  = os.path.splitext(f.filename)[1].lower()
    if not re.fullmatch(r"\.[a-z0-9]{1,6}", ext or ""):
        return jsonify({"error": "invalid extension"}), 400
    name = uuid.uuid4().hex + ext
    path = os.path.abspath(os.path.join(_upload_dir(), name))
    f.save(path)
    log.info("upload_file: %s -> %s (%d bytes)", f.filename, name, os.path.getsize(path))
    return jsonify({"ok": True, "filename": name, "path": path,
                    "original": f.filename, "size": os.path.getsize(path)})


@upload_bp.route("/image/restyle", methods=["POST"])
@login_required
def image_restyle():
    """Convert an uploaded image into a styled version (ghibli/anime/...)."""
    from services.image_restyle import restyle
    b = request.get_json(force=True) or {}
    b64 = b.get("image_b64", "")
    if not b64:
        return jsonify({"error": "image_b64 required"}), 400
    return jsonify(restyle(b64, b.get("style", "ghibli"), b.get("mime", "image/jpeg")))


@upload_bp.route("/uploads/<path:filename>")
def serve_upload(filename):
    if re.search(r"[/\\\.]{2,}|^\.", filename):
        return jsonify({"error": "invalid"}), 400
    return send_from_directory(_upload_dir(), filename)


@upload_bp.route("/screenshot", methods=["POST"])
@login_required
@no_guests
def web_screenshot():
    log.info("screenshot: user=%s", current_user())
    try:
        from PIL import ImageGrab
        fname = "screenshot_%d.png" % int(time.time())
        path  = os.path.join(_upload_dir(), fname)
        ImageGrab.grab().save(path)
        return jsonify({"url": "/uploads/%s" % fname, "fname": fname})
    except ImportError:
        return jsonify({"error": "pip install pillow"}), 500
    except Exception as e:
        log.error("screenshot failed: %s", e)
        return jsonify({"error": str(e)}), 500


@upload_bp.route("/logo")
def serve_logo():
    from flask import send_file
    import io
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    logo_path = os.path.join(base, "aiaurum_logo.png")
    if os.path.exists(logo_path):
        return send_file(logo_path, mimetype="image/png")
    # placeholder 1×1 transparent PNG
    data = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    )
    return send_file(io.BytesIO(data), mimetype="image/png")
