"""TTS/STT provider interfaces."""
from __future__ import annotations

import abc
from typing import Any, Dict, List, Optional


class TTSProvider(abc.ABC):
    """Text-to-Speech provider."""

    @property
    @abc.abstractmethod
    def name(self) -> str:
        ...

    def is_available(self) -> bool:
        return True

    @abc.abstractmethod
    def synthesize(self, text: str, **kwargs) -> Dict[str, Any]:
        """Synthesize speech from text. Return dict with 'audio' key (file path)."""


class STTProvider(abc.ABC):
    """Speech-to-Text provider."""

    @property
    @abc.abstractmethod
    def name(self) -> str:
        ...

    def is_available(self) -> bool:
        return True

    @abc.abstractmethod
    def transcribe(self, audio_path: str, **kwargs) -> Dict[str, Any]:
        """Transcribe audio file to text."""
