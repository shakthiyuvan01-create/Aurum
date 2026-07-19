"""
Image Generation Provider ABC — pluggable backend interface for image generation.

Port of Hermes agent/image_gen_provider.py adapted for Aurum.
"""
from __future__ import annotations

import abc
import base64
import datetime
import logging
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

VALID_ASPECT_RATIOS: Tuple[str, ...] = ("landscape", "square", "portrait")
DEFAULT_ASPECT_RATIO = "landscape"


class ImageGenProvider(abc.ABC):
    """Abstract base class for an image generation backend."""

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Stable short identifier, lowercase, no spaces."""

    @property
    def display_name(self) -> str:
        return self.name.title()

    def is_available(self) -> bool:
        return True

    def list_models(self) -> List[Dict[str, Any]]:
        return []

    def default_model(self) -> Optional[str]:
        models = self.list_models()
        return models[0].get("id") if models else None

    def capabilities(self) -> Dict[str, Any]:
        return {"modalities": ["text"], "max_reference_images": 0}

    @abc.abstractmethod
    def generate(
        self,
        prompt: str,
        aspect_ratio: str = DEFAULT_ASPECT_RATIO,
        *,
        image_url: Optional[str] = None,
        reference_image_urls: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Generate an image from a text prompt, or edit/transform a source image."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def resolve_aspect_ratio(value: Optional[str]) -> str:
    if not isinstance(value, str):
        return DEFAULT_ASPECT_RATIO
    v = value.strip().lower()
    return v if v in VALID_ASPECT_RATIOS else DEFAULT_ASPECT_RATIO


def normalize_reference_images(value: Any) -> Optional[List[str]]:
    if value is None:
        return None
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple)):
        return None
    out: List[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            out.append(item.strip())
    return out or None


def save_b64_image(
    b64_data: str,
    *,
    prefix: str = "image",
    extension: str = "png",
    save_dir: Optional[str] = None,
) -> str:
    """Decode base64 image data and write to disk. Returns absolute path."""
    raw = base64.b64decode(b64_data)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    short = uuid.uuid4().hex[:8]
    if save_dir is None:
        import os
        save_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads")
    Path(save_dir).mkdir(parents=True, exist_ok=True)
    path = Path(save_dir) / f"{prefix}_{ts}_{short}.{extension}"
    path.write_bytes(raw)
    return str(path)


def save_url_image(
    url: str,
    *,
    prefix: str = "image",
    timeout: float = 60.0,
    max_bytes: int = 25 * 1024 * 1024,
    save_dir: Optional[str] = None,
) -> str:
    """Download an image URL and save to disk. Returns absolute path."""
    import requests
    resp = requests.get(url, timeout=timeout, stream=True)
    resp.raise_for_status()
    if save_dir is None:
        import os
        save_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads")
    Path(save_dir).mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    short = uuid.uuid4().hex[:8]
    path = Path(save_dir) / f"{prefix}_{ts}_{short}.png"
    bytes_written = 0
    with path.open("wb") as fh:
        for chunk in resp.iter_content(chunk_size=64 * 1024):
            if not chunk:
                continue
            bytes_written += len(chunk)
            if bytes_written > max_bytes:
                fh.close()
                path.unlink()
                raise ValueError(f"Image exceeds {max_bytes // (1024*1024)}MB cap")
            fh.write(chunk)
    return str(path)


def success_response(
    *,
    image: str,
    model: str,
    prompt: str,
    aspect_ratio: str,
    provider: str,
    modality: str = "text",
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "success": True,
        "image": image,
        "model": model,
        "prompt": prompt,
        "aspect_ratio": aspect_ratio,
        "modality": modality,
        "provider": provider,
    }
    if extra:
        payload.update(extra)
    return payload


def error_response(
    *,
    error: str,
    error_type: str = "provider_error",
    provider: str = "",
    model: str = "",
    prompt: str = "",
    aspect_ratio: str = DEFAULT_ASPECT_RATIO,
) -> Dict[str, Any]:
    return {
        "success": False,
        "image": None,
        "error": error,
        "error_type": error_type,
        "model": model,
        "prompt": prompt,
        "aspect_ratio": aspect_ratio,
        "provider": provider,
    }
