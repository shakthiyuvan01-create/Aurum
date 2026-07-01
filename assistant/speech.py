"""assistant/speech.py — TTS, say(), alert()."""
import logging
import os
import subprocess
from assistant.config import SPEAK_REPLIES, SHOW_NOTIFICATIONS, SPEAK_ALERTS

log = logging.getLogger("assistant.speech")

try:
    from plyer import notification as _notifier
except ImportError:
    _notifier = None

# Overrideable by app.py (wires in edge-tts or ElevenLabs)
speak = None


def _powershell_speak(text: str) -> bool:
    try:
        clean = text.replace('"', '').replace("'", "")[:300]
        cmd   = (
            'Add-Type -AssemblyName System.Speech; '
            f'(New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak("{clean}")'
        )
        subprocess.Popen(
            ["powershell", "-Command", cmd],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        return True
    except Exception:
        return False


def say(text: str) -> None:
    if speak and callable(speak):
        try:
            speak(text)
            return
        except Exception as e:
            log.debug("speak() failed: %s", e)
    if SPEAK_REPLIES and os.name == "nt":
        _powershell_speak(text)


def alert(title: str, message: str, speak_it: bool = True) -> None:
    if SHOW_NOTIFICATIONS and _notifier:
        try:
            _notifier.notify(title=title, message=message[:250], timeout=8)
        except Exception:
            pass
    if speak_it and SPEAK_ALERTS:
        say(message)
    log.info("ALERT: %s — %s", title, message)
