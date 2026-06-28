"""
services/speech_service.py — TTS (Windows SAPI) and STT helpers
"""
import os, threading, subprocess, logging

log = logging.getLogger("services.speech")

_speech_proc = None
_speech_lock = threading.Lock()


def speak(text: str) -> None:
    """Speak text using Windows SAPI (PowerShell). No-op on non-Windows."""
    global _speech_proc
    if not text or os.name != "nt":
        return
    safe = text.replace("'", "''")
    cmd  = (
        "Add-Type -AssemblyName System.Speech;"
        "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;"
        "$s.Rate=-1;$s.Speak('%s')" % safe
    )
    with _speech_lock:
        if _speech_proc and _speech_proc.poll() is None:
            _speech_proc.kill()
        _speech_proc = subprocess.Popen(
            ["powershell", "-NoProfile", "-Command", cmd],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    _speech_proc.wait()


def stop() -> None:
    """Stop any ongoing speech."""
    global _speech_proc
    with _speech_lock:
        if _speech_proc and _speech_proc.poll() is None:
            _speech_proc.kill()
            _speech_proc = None


def generate_tts_audio(text: str, voice: str = "en-US-GuyNeural") -> bytes | None:
    """
    Generate TTS audio bytes using edge-tts (async).
    Returns MP3 bytes or None on failure.
    """
    try:
        import asyncio, edge_tts, io
        async def _gen():
            buf = io.BytesIO()
            async for chunk in edge_tts.Communicate(text, voice).stream():
                if chunk["type"] == "audio":
                    buf.write(chunk["data"])
            return buf.getvalue()
        return asyncio.run(_gen())
    except Exception as e:
        log.warning("edge-tts failed: %s", e)
        return None
