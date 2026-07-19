"""Image Generation System — provider-based, multi-backend.

Port of the Hermes image generation framework adapted for Aurum.
Supports text-to-image and image-to-image via pluggable backends.
"""
from image_gen.registry import ImageGenRegistry, get_registry
from image_gen.provider import ImageGenProvider

__all__ = ["ImageGenRegistry", "ImageGenProvider", "get_registry"]
