"""Video generation tool — unified surface for all backends."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# In-memory registry
_providers: Dict[str, Any] = {}


def register_provider(provider) -> None:
    _providers[provider.name] = provider
    logger.debug("Registered video provider '%s'", provider.name)


def list_video_providers() -> List[Dict[str, Any]]:
    return [
        {"name": p.name, "display_name": p.display_name,
         "available": p.is_available(), "models": p.list_models()}
        for p in _providers.values()
    ]


def generate_video(
    prompt: str,
    *,
    provider: Optional[str] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Generate a video using the best available provider."""
    # Check for FAL key first (most common)
    if not provider:
        for name in ["fal", "deepinfra"]:
            if name in _providers and _providers[name].is_available():
                provider = name
                break

    if not provider or provider not in _providers:
        return {
            "success": False,
            "error": "No video provider available. Set FAL_KEY or DEEPINFRA_API_KEY.",
        }

    active = _providers[provider]
    logger.info("Generating video via %s", active.name)
    return active.generate(prompt=prompt, **kwargs)


# Auto-register backends
try:
    from video_gen.backends.fal import FalVideoProvider
    register_provider(FalVideoProvider())
except Exception:
    pass

try:
    from video_gen.backends.xai import XAIVideoProvider
    register_provider(XAIVideoProvider())
except Exception:
    pass
