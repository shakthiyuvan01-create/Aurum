"""TTS/STT tool — unified surface for all backends."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from tts.provider import TTSProvider, STTProvider

logger = logging.getLogger(__name__)

_tts_providers: Dict[str, TTSProvider] = {}
_stt_providers: Dict[str, STTProvider] = {}


def register_tts_provider(provider: TTSProvider) -> None:
    _tts_providers[provider.name] = provider
    logger.debug("Registered TTS provider '%s'", provider.name)


def register_stt_provider(provider: STTProvider) -> None:
    _stt_providers[provider.name] = provider
    logger.debug("Registered STT provider '%s'", provider.name)


def list_tts_providers() -> List[Dict[str, Any]]:
    return [
        {"name": p.name, "available": p.is_available()}
        for p in _tts_providers.values()
    ]


def text_to_speech(text: str, provider: Optional[str] = None, **kwargs) -> Optional[str]:
    """Convert text to speech. Returns path to audio file, or None."""
    if not provider:
        for p in _tts_providers.values():
            if p.is_available():
                provider = p.name
                break
    if not provider or provider not in _tts_providers:
        logger.warning("No TTS provider available")
        return None
    result = _tts_providers[provider].synthesize(text, **kwargs)
    if result.get("success"):
        return result.get("audio")
    logger.warning("TTS failed: %s", result.get("error"))
    return None


def speech_to_text(audio_path: str, provider: Optional[str] = None, **kwargs) -> Optional[str]:
    """Transcribe audio to text. Returns text, or None."""
    if not provider:
        for p in _stt_providers.values():
            if p.is_available():
                provider = p.name
                break
    if not provider or provider not in _stt_providers:
        logger.warning("No STT provider available")
        return None
    result = _stt_providers[provider].transcribe(audio_path, **kwargs)
    if result.get("success"):
        return result.get("text")
    logger.warning("STT failed: %s", result.get("error"))
    return None


# Auto-register available providers
try:
    from tts.backends.windows import WindowsTTSProvider
    register_tts_provider(WindowsTTSProvider())
except Exception:
    pass

try:
    from tts.backends.openai_tts import OpenAITTSProvider
    register_tts_provider(OpenAITTSProvider())
except Exception:
    pass
