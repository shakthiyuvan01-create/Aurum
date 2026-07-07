"""
services/voice_service.py — Voice Assistant service.
Supports: STT via Whisper, TTS via edge-tts/ElevenLabs,
wake word detection, streaming, multilingual.
"""
from __future__ import annotations
import io, logging, os, threading, time
from typing import Callable, Optional

log = logging.getLogger("services.voice")

_ELEVEN_VOICE_CACHE = None


def _elevenlabs_pick_voice(key: str, force: bool = False) -> str:
    """Find a voice this account can ACTUALLY use: list account voices and
    live-test candidates with a 1-word request until one returns 200."""
    global _ELEVEN_VOICE_CACHE
    if _ELEVEN_VOICE_CACHE and not force:
        return _ELEVEN_VOICE_CACHE
    try:
        import requests as _rq
        r = _rq.get("https://api.elevenlabs.io/v1/voices",
                    headers={"xi-api-key": key}, timeout=15)
        if r.status_code != 200:
            log.warning("ElevenLabs /voices failed: HTTP %d %s",
                        r.status_code, r.text[:120])
            return "21m00Tcm4TlvDq8ikWAM"
        voices = r.json().get("voices", [])
        log.info("ElevenLabs account has %d voices: %s", len(voices),
                 ", ".join("%s(%s)" % (v.get("name"), v.get("category"))
                           for v in voices[:8]))
        cloned  = [v for v in voices if v.get("category") == "cloned"]
        premade = [v for v in voices if v.get("category") == "premade"]
        candidates = (cloned + premade + voices)[:4]
        model_id = os.getenv("ELEVENLABS_MODEL", "eleven_multilingual_v2")
        for v in candidates:
            try:
                t = _rq.post(
                    "https://api.elevenlabs.io/v1/text-to-speech/%s" % v["voice_id"],
                    headers={"xi-api-key": key, "Content-Type": "application/json"},
                    json={"text": "ok", "model_id": model_id}, timeout=20)
                if t.status_code == 200:
                    _ELEVEN_VOICE_CACHE = v["voice_id"]
                    log.info("ElevenLabs USABLE voice found: %s (%s)",
                             v.get("name"), v.get("category"))
                    return _ELEVEN_VOICE_CACHE
                log.warning("voice %s (%s) rejected: HTTP %d", v.get("name"),
                            v.get("category"), t.status_code)
            except Exception as te:
                log.debug("voice test error: %s", te)
        log.warning("ElevenLabs: NO usable voice on this plan - "
                    "falling back to edge-tts permanently this session")
        _ELEVEN_VOICE_CACHE = "NONE"
    except Exception as e:
        log.warning("voice pick failed: %s", e)
    return _ELEVEN_VOICE_CACHE or "21m00Tcm4TlvDq8ikWAM"

_VOSK_MODEL = None  # cached vosk model (68MB - load once)


# ── STT — Speech-to-Text ──────────────────────────────────────────────────────
def transcribe(audio_path: str, language: str = "en") -> dict:
    """
    Transcribe audio file to text.
    Tries: OpenAI Whisper API → local whisper → vosk → error
    """
    # Try OpenAI Whisper API
    api_key = os.getenv("OPENAI_API_KEY", "")
    if api_key:
        try:
            import requests
            with open(audio_path, "rb") as f:
                r = requests.post(
                    "https://api.openai.com/v1/audio/transcriptions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    files={"file": (os.path.basename(audio_path), f)},
                    data={"model": "whisper-1", "language": language},
                    timeout=60,
                )
            if r.status_code == 200:
                text = r.json().get("text", "")
                return {"text": text, "language": language, "backend": "whisper-api"}
        except Exception as e:
            log.warning("Whisper API failed: %s", e)

    # Try local whisper
    try:
        import whisper
        model = whisper.load_model("base")
        result = model.transcribe(audio_path, language=language if language != "auto" else None)
        return {"text": result["text"], "language": result.get("language", language), "backend": "whisper-local"}
    except ImportError:
        pass
    except Exception as e:
        log.warning("Local whisper failed: %s", e)

    # Try vosk (offline, uses ./model directory)
    try:
        import wave, json as _json, shutil, subprocess
        from vosk import Model, KaldiRecognizer
        model_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "model")
        if os.path.isdir(model_dir):
            wav_path = audio_path
            conv = None
            if shutil.which("ffmpeg"):
                conv = audio_path + ".conv.wav"
                subprocess.run(
                    ["ffmpeg", "-y", "-i", audio_path, "-ar", "16000", "-ac", "1", "-f", "wav", conv],
                    capture_output=True, timeout=60,
                )
                if os.path.exists(conv) and os.path.getsize(conv) > 44:
                    wav_path = conv
            global _VOSK_MODEL
            if _VOSK_MODEL is None:
                _VOSK_MODEL = Model(model_dir)
            wf = wave.open(wav_path, "rb")
            rec = KaldiRecognizer(_VOSK_MODEL, wf.getframerate())
            parts = []
            while True:
                data = wf.readframes(4000)
                if not data:
                    break
                if rec.AcceptWaveform(data):
                    parts.append(_json.loads(rec.Result()).get("text", ""))
            parts.append(_json.loads(rec.FinalResult()).get("text", ""))
            wf.close()
            if conv and os.path.exists(conv):
                os.unlink(conv)
            text = " ".join(p for p in parts if p).strip()
            if text:
                return {"text": text, "language": language, "backend": "vosk"}
    except ImportError:
        pass
    except Exception as e:
        log.warning("vosk failed: %s", e)

    return {"error": "No STT backend available. Install: pip install openai-whisper OR set OPENAI_API_KEY"}


# ── TTS — Text-to-Speech ──────────────────────────────────────────────────────
def speak(text: str, voice: str = "en-US-AriaNeural", output_path: str = None) -> dict:
    """
    Convert text to speech.
    Tries: ElevenLabs → edge-tts → pyttsx3 → error
    """
    # ElevenLabs
    elabs_key = os.getenv("ELEVENLABS_API_KEY", "")
    if elabs_key:
        try:
            import requests
            voice_id = os.getenv("ELEVENLABS_VOICE_ID") or _elevenlabs_pick_voice(elabs_key)
            if voice_id == "NONE":
                raise RuntimeError("no API-usable ElevenLabs voice on this plan")
            model_id = os.getenv("ELEVENLABS_MODEL", "eleven_multilingual_v2")
            r = requests.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream",
                headers={"xi-api-key": elabs_key, "Content-Type": "application/json"},
                json={"text": text, "model_id": model_id,
                      "voice_settings": {"stability": 0.5, "similarity_boost": 0.8}},
                timeout=30,
            )
            if r.status_code in (402, 403, 404):
                # configured voice not allowed on this plan -> use an account voice
                log.warning("ElevenLabs voice %s rejected (%d), picking an "
                            "account voice", voice_id, r.status_code)
                alt = _elevenlabs_pick_voice(elabs_key, force=True)
                if alt and alt != voice_id:
                    r = requests.post(
                        f"https://api.elevenlabs.io/v1/text-to-speech/{alt}/stream",
                        headers={"xi-api-key": elabs_key, "Content-Type": "application/json"},
                        json={"text": text, "model_id": model_id,
                              "voice_settings": {"stability": 0.5, "similarity_boost": 0.8}},
                        timeout=30,
                    )
            if r.status_code != 200:
                log.warning("ElevenLabs HTTP %d: %s", r.status_code, r.text[:200])
            if r.status_code == 200:
                out = output_path or "/tmp/tts_output.mp3"
                with open(out, "wb") as f:
                    f.write(r.content)
                return {"audio_path": out, "backend": "elevenlabs"}
        except Exception as e:
            log.warning("ElevenLabs failed: %s", e)

    # edge-tts (free, high quality)
    try:
        import asyncio
        import edge_tts
        out = output_path or "/tmp/tts_output.mp3"

        async def _run():
            comm = edge_tts.Communicate(text, voice)
            await comm.save(out)

        asyncio.run(_run())
        return {"audio_path": out, "backend": "edge-tts", "voice": voice}
    except ImportError:
        pass
    except Exception as e:
        log.warning("edge-tts failed: %s", e)

    # pyttsx3 fallback
    try:
        import pyttsx3
        engine = pyttsx3.init()
        out    = output_path or "/tmp/tts_output.wav"
        engine.save_to_file(text, out)
        engine.runAndWait()
        return {"audio_path": out, "backend": "pyttsx3"}
    except Exception as e:
        log.warning("pyttsx3 failed: %s", e)

    return {"error": "No TTS backend available. Install: pip install edge-tts OR set ELEVENLABS_API_KEY"}


def list_voices() -> list[dict]:
    """List available edge-tts voices."""
    try:
        import asyncio, edge_tts

        async def _get():
            return await edge_tts.list_voices()

        voices = asyncio.run(_get())
        return [{"name": v["ShortName"], "locale": v["Locale"], "gender": v["Gender"]} for v in voices[:50]]
    except Exception:
        return [
            {"name": "en-US-AriaNeural",   "locale": "en-US", "gender": "Female"},
            {"name": "en-US-GuyNeural",    "locale": "en-US", "gender": "Male"},
            {"name": "en-GB-SoniaNeural",  "locale": "en-GB", "gender": "Female"},
            {"name": "hi-IN-SwaraNeural",  "locale": "hi-IN", "gender": "Female"},
            {"name": "te-IN-ShrutiNeural", "locale": "te-IN", "gender": "Female"},
        ]


# ── Wake word detection ────────────────────────────────────────────────────────
_WAKE_WORDS = ["hey aurum", "hi aurum", "aurum", "ok aurum"]
_listening  = threading.Event()
_wake_callbacks: list[Callable] = []


def add_wake_callback(fn: Callable) -> None:
    _wake_callbacks.append(fn)


def _contains_wake_word(text: str) -> bool:
    t = text.lower().strip()
    return any(w in t for w in _WAKE_WORDS)


def start_listening(device_index: int = None):
    """
    Start continuous microphone listening.
    Calls registered wake-word callbacks when wake word is detected.
    Requires pyaudio + local whisper.
    """
    try:
        import pyaudio, wave, tempfile, struct, math
    except ImportError:
        log.warning("pyaudio not installed — continuous listening unavailable")
        return

    _listening.set()
    CHUNK     = 1024
    FORMAT    = pyaudio.paInt16
    CHANNELS  = 1
    RATE      = 16000
    THRESHOLD = 500
    SILENCE   = 1.5    # seconds of silence to end utterance

    def _rms(data):
        shorts = struct.unpack(f"{len(data)//2}h", data)
        return math.sqrt(sum(s*s for s in shorts) / len(shorts))

    def _listener():
        pa      = pyaudio.PyAudio()
        stream  = pa.open(format=FORMAT, channels=CHANNELS, rate=RATE,
                          input=True, input_device_index=device_index,
                          frames_per_buffer=CHUNK)
        log.info("Voice listener started")
        frames      = []
        recording   = False
        silent_since = None

        while _listening.is_set():
            data  = stream.read(CHUNK, exception_on_overflow=False)
            level = _rms(data)
            if level > THRESHOLD:
                recording    = True
                silent_since = None
                frames.append(data)
            elif recording:
                frames.append(data)
                if silent_since is None:
                    silent_since = time.time()
                elif time.time() - silent_since > SILENCE:
                    # Save + transcribe
                    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                        wf = wave.open(tmp.name, "wb")
                        wf.setnchannels(CHANNELS)
                        wf.setsampwidth(pa.get_sample_size(FORMAT))
                        wf.setframerate(RATE)
                        wf.writeframes(b"".join(frames))
                        wf.close()
                        result = transcribe(tmp.name)
                    text = result.get("text", "")
                    if text and _contains_wake_word(text):
                        clean = text
                        for w in _WAKE_WORDS:
                            clean = clean.lower().replace(w, "").strip()
                        for cb in _wake_callbacks:
                            try: cb(clean)
                            except Exception: pass
                    frames      = []
                    recording   = False
                    silent_since= None

        stream.stop_stream()
        stream.close()
        pa.terminate()

    t = threading.Thread(target=_listener, daemon=True)
    t.start()
    return t


def stop_listening():
    _listening.clear()
