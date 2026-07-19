"""OpenAI TTS backend."""
from __future__ import annotations

import logging
import os
import tempfile
from typing import Any, Dict, Optional

from tts.provider import TTSProvider

logger = logging.getLogger(__name__)

OPENAI_VOICES = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]


class OpenAITTSProvider(TTSProvider):
    """OpenAI TTS using the speech API."""

    @property
    def name(self) -> str:
        return "openai"

    def is_available(self) -> bool:
        return bool(os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENAI_KEY"))

    def synthesize(self, text: str, **kwargs) -> Dict[str, Any]:
        api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENAI_KEY")
        if not api_key:
            return {"success": False, "error": "No OpenAI API key"}

        voice = kwargs.get("voice", "alloy")
        model = kwargs.get("model", "tts-1")
        if voice not in OPENAI_VOICES:
            voice = "alloy"

        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key)
            response = client.audio.speech.create(model=model, voice=voice, input=text)

            out_dir = kwargs.get("save_dir") or tempfile.gettempdir()
            os.makedirs(out_dir, exist_ok=True)
            out_path = os.path.join(out_dir, f"tts_openai_{hash(text) % 100000}.mp3")
            response.stream_to_file(out_path)
            return {"success": True, "audio": out_path, "text": text}
        except Exception as exc:
            return {"success": False, "error": str(exc)}
