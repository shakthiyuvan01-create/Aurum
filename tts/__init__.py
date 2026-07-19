"""Text-to-Speech and Speech-to-Text enhancements.

Port of Hermes' TTS/voice system adapted for Aurum.
"""
from tts.provider import TTSProvider, STTProvider
from tts.tool import (
    text_to_speech, speech_to_text, list_tts_providers,
    register_tts_provider, register_stt_provider,
)

__all__ = [
    "TTSProvider", "STTProvider",
    "text_to_speech", "speech_to_text", "list_tts_providers",
    "register_tts_provider", "register_stt_provider",
]
