"""
Image Generation Provider Registry — central map of registered providers.

Port of Hermes agent/image_gen_registry.py adapted for Aurum.
"""
from __future__ import annotations

import logging
import threading
from typing import Any, Dict, List, Optional

from image_gen.provider import ImageGenProvider

logger = logging.getLogger(__name__)


class ImageGenRegistry:
    """Thread-safe registry for image generation providers."""

    def __init__(self):
        self._providers: Dict[str, ImageGenProvider] = {}
        self._lock = threading.Lock()

    def register(self, provider: ImageGenProvider) -> None:
        if not isinstance(provider, ImageGenProvider):
            raise TypeError(f"Expected ImageGenProvider, got {type(provider).__name__}")
        name = provider.name
        with self._lock:
            self._providers[name] = provider
        logger.debug("Registered image gen provider '%s' (%s)", name, type(provider).__name__)

    def unregister(self, name: str) -> None:
        with self._lock:
            self._providers.pop(name, None)

    def list_providers(self) -> List[ImageGenProvider]:
        with self._lock:
            return list(self._providers.values())

    def get_provider(self, name: str) -> Optional[ImageGenProvider]:
        with self._lock:
            return self._providers.get(name)

    def get_active(self, preferred: Optional[str] = None) -> Optional[ImageGenProvider]:
        """Get the active provider. Uses preferred name, or first available."""
        if preferred:
            p = self.get_provider(preferred)
            if p and p.is_available():
                return p
        # Fallback: return first available
        for p in self.list_providers():
            if p.is_available():
                return p
        return None


# Global singleton
_global_registry: Optional[ImageGenRegistry] = None
_global_lock = threading.Lock()


def get_registry() -> ImageGenRegistry:
    global _global_registry
    if _global_registry is None:
        with _global_lock:
            if _global_registry is None:
                _global_registry = ImageGenRegistry()
    return _global_registry


def register_provider(provider: ImageGenProvider) -> None:
    get_registry().register(provider)


def list_providers() -> List[ImageGenProvider]:
    return get_registry().list_providers()


def get_active_provider(preferred: Optional[str] = None) -> Optional[ImageGenProvider]:
    return get_registry().get_active(preferred)
