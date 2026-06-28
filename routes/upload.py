"""
routes/upload.py — image upload, file serving, screenshot
"""
import os, uuid, re, time, base64, logging
from flask import Blueprint, request, jsonify, send_from_directory
from services.auth_service import login_required, current_user

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


@upload_bp.route("/uploads/<path:filename>")
def serve_upload(filename):
    if re.search(r"[/\\\.]{2,}|^\.", filename):
        return jsonify({"error": "invalid"}), 400
    return send_from_directory(_upload_dir(), filename)


@upload_bp.route("/screenshot", methods=["POST"])
@login_required
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
    logo_path = os.path.join(base, "assistneo_logo.png")
    if os.path.exists(logo_path):
        return send_file(logo_path, mimetype="image/png")
    # placeholder 1×1 transparent PNG
    data = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    )
    return send_file(io.BytesIO(data), mimetype="image/png")
