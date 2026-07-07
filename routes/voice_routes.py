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
    # Windows fix: NamedTemporaryFile keeps the handle OPEN inside the with-
    # block, so ElevenLabs/edge-tts could not write to it (PermissionError)
    # and TTS silently fell back to the robotic device voice.
    import uuid as _uuid
    tmp_path = os.path.join(tempfile.gettempdir(), "tts_" + _uuid.uuid4().hex + ".mp3")
    result = _vs.speak(text, voice=voice, output_path=tmp_path)
    if "error" in result:
        log.warning("TTS failed: %s", result["error"])
        return jsonify(result), 500
    log.info("TTS backend: %s", result.get("backend", "?"))
    resp = send_file(result["audio_path"], mimetype="audio/mpeg",
                     as_attachment=True, download_name="speech.mp3")
    resp.headers["X-TTS-Backend"] = result.get("backend", "?")
    return resp


@voice_bp.route("/voice/voices")
def list_voices():
    import services.voice_service as _vs
    return jsonify({"voices": _vs.list_voices()})


@voice_bp.route("/voice/test")
@login_required
def voice_test():
    """Diagnose the TTS chain: is ElevenLabs working? Which voices do you have?"""
    import os as _os, requests as _rq
    out = {"elevenlabs_key_set": bool(_os.getenv("ELEVENLABS_API_KEY", "")),
           "active_voice_id": _os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM (Rachel, default)"),
           "model": _os.getenv("ELEVENLABS_MODEL", "eleven_multilingual_v2")}
    key = _os.getenv("ELEVENLABS_API_KEY", "")
    if key:
        try:
            r = _rq.get("https://api.elevenlabs.io/v1/voices",
                        headers={"xi-api-key": key}, timeout=20)
            if r.status_code == 200:
                out["elevenlabs"] = "WORKING"
                out["your_voices"] = [
                    {"name": v["name"], "voice_id": v["voice_id"],
                     "category": v.get("category", "")}
                    for v in r.json().get("voices", [])[:20]]
                try:
                    s = _rq.get("https://api.elevenlabs.io/v1/user/subscription",
                                headers={"xi-api-key": key}, timeout=15).json()
                    out["quota"] = "%s / %s characters used" % (
                        s.get("character_count", "?"), s.get("character_limit", "?"))
                except Exception:
                    pass
            else:
                out["elevenlabs"] = "FAILED: HTTP %d %s" % (r.status_code, r.text[:150])
        except Exception as e:
            out["elevenlabs"] = "FAILED: %s" % str(e)[:150]
    else:
        out["elevenlabs"] = "no key - set ELEVENLABS_API_KEY"
    out["fallback_chain"] = "ElevenLabs -> edge-tts (free) -> device voice"
    out["how_to_change_voice"] = ("pick a voice_id from your_voices and set "
                                  "ELEVENLABS_VOICE_ID=<id> in .env, then restart")
    return jsonify(out)
