"""Image generation tool — unified surface for all backends."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from image_gen.registry import get_registry, register_provider
from image_gen.provider import (
    DEFAULT_ASPECT_RATIO,
    error_response,
    resolve_aspect_ratio,
)

logger = logging.getLogger(__name__)


# Auto-register available backends
def _auto_register():
    try:
        from image_gen.backends.pollinations import PollinationsProvider
        register_provider(PollinationsProvider())
    except Exception as e:
        logger.debug("Could not register Pollinations: %s", e)

    try:
        from image_gen.backends.openai import OpenAIImageProvider
        register_provider(OpenAIImageProvider())
    except Exception as e:
        logger.debug("Could not register OpenAI: %s", e)

    try:
        from image_gen.backends.fal import FalImageProvider
        register_provider(FalImageProvider())
    except Exception as e:
        logger.debug("Could not register FAL: %s", e)

    try:
        from image_gen.backends.deepinfra import DeepInfraProvider
        register_provider(DeepInfraProvider())
    except Exception as e:
        logger.debug("Could not register DeepInfra: %s", e)


_auto_register()


def list_available_providers() -> List[Dict[str, Any]]:
    """List all registered providers with their availability."""
    from image_gen.registry import list_providers
    result = []
    for p in list_providers():
        result.append({
            "name": p.name,
            "display_name": p.display_name,
            "available": p.is_available(),
            "models": p.list_models(),
            "default_model": p.default_model(),
            "capabilities": p.capabilities(),
        })
    return result


def generate_image(
    prompt: str,
    aspect_ratio: str = DEFAULT_ASPECT_RATIO,
    *,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    image_url: Optional[str] = None,
    reference_image_urls: Optional[List[str]] = None,
    save_dir: Optional[str] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Generate an image using the best available provider.

    Args:
        prompt: Text description of the image to generate
        aspect_ratio: "landscape", "square", or "portrait"
        provider: Preferred provider name (auto-selected if None)
        model: Model identifier for the provider
        image_url: Source image for editing (if supported)
        reference_image_urls: Additional reference images
        save_dir: Directory to save the image (defaults to uploads/)
        **kwargs: Additional provider-specific parameters

    Returns:
        Dict with keys: success, image (path), model, prompt, aspect_ratio, provider
    """
    from image_gen.registry import get_active_provider

    active = get_active_provider(provider)
    if not active:
        available = list_available_providers()
        names = [p["display_name"] for p in available]
        return error_response(
            error=f"No image generation provider available. Configured providers: {names or 'none'}",
            error_type="no_provider",
            aspect_ratio=resolve_aspect_ratio(aspect_ratio),
        )

    gen_kwargs = dict(kwargs)
    if model:
        gen_kwargs["model"] = model
    if save_dir:
        gen_kwargs["save_dir"] = save_dir

    logger.info("Generating image via %s with model %s", active.name, model or "default")
    return active.generate(
        prompt=prompt,
        aspect_ratio=aspect_ratio,
        image_url=image_url,
        reference_image_urls=reference_image_urls,
        **gen_kwargs,
    )
