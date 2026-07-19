"""Windows built-in TTS via SAPI / PowerShell."""
from __future__ import annotations

import logging
import os
import subprocess
import tempfile
from typing import Any, Dict

from tts.provider import TTSProvider

logger = logging.getLogger(__name__)


class WindowsTTSProvider(TTSProvider):
    """Windows built-in TTS using PowerShell."""

    @property
    def name(self) -> str:
        return "windows"

    def is_available(self) -> bool:
        return os.name == "nt"

    def synthesize(self, text: str, **kwargs) -> Dict[str, Any]:
        try:
            from assistant.speech import _powershell_speak
            result = _powershell_speak(text, wait=False)
            return {"success": True, "audio": "spoken", "text": text}
        except Exception as exc:
            return {"success": False, "error": str(exc)}
