"""routes/voice_routes.py — Voice assistant API endpoints."""
import os, tempfile, logging
from flask import Blueprint, request, jsonify, send_file, session
from services.auth_service import login_required

voice_bp = Blueprint("voice", __name__)
log = logging.getLogger("routes.voice")

_deps: dict = {}

def _init(deps: dict) -> None:
    _deps.update(deps)


@voice_bp.route("/voice/transcribe", methods=["POST"])
@login_required
def transcribe_audio():
    """Transcribe uploaded audio file."""
    import services.voice_service as _vs
    if "audio" not in request.files:
        return jsonify({"error": "No audio file uploaded"}), 400
    audio_file = request.files["audio"]
    language   = request.form.get("language", "en")
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        audio_file.save(tmp.name)
        result = _vs.transcribe(tmp.name, language)
    os.unlink(tmp.name)
    return jsonify(result)


@voice_bp.route("/voice/speak", methods=["POST"])
@login_required
def text_to_speech():
    """Convert text to speech and return audio file."""
    import services.voice_service as _vs
    data  = request.get_json(force=True) or {}
    text  = (data.get("text") or "").strip()
    voice = data.get("voice", "en-US-AriaNeural")
    if not text:
        return jsonify({"error": "text required"}), 400
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        result = _vs.speak(text, voice=voice, output_path=tmp.name)
    if "error" in result:
        return jsonify(result), 500
    return send_file(result["audio_path"], mimetype="audio/mpeg",
                     as_attachment=True, download_name="speech.mp3")


@voice_bp.route("/voice/voices")
def list_voices():
    import services.voice_service as _vs
    return jsonify({"voices": _vs.list_voices()})
