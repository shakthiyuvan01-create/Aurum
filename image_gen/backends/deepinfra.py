"""
Simple image download backend.
Wraps a URL-based image generation API (like HuggingFace, DeepInfra, etc.).
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

import requests

from image_gen.provider import (
    DEFAULT_ASPECT_RATIO,
    ImageGenProvider,
    error_response,
    resolve_aspect_ratio,
    save_url_image,
    success_response,
)

logger = logging.getLogger(__name__)


class DeepInfraProvider(ImageGenProvider):
    """DeepInfra image generation via their REST API."""

    @property
    def name(self) -> str:
        return "deepinfra"

    @property
    def display_name(self) -> str:
        return "DeepInfra"

    def is_available(self) -> bool:
        return bool(os.environ.get("DEEPINFRA_API_KEY"))

    def list_models(self) -> List[Dict[str, Any]]:
        return [
            {"id": "black-forest-labs/FLUX-1.1-pro", "display": "FLUX 1.1 Pro", "speed": "~10s"},
            {"id": "black-forest-labs/FLUX-1-schnell", "display": "FLUX Schnell", "speed": "~3s"},
            {"id": "stabilityai/stable-diffusion-3.5-large", "display": "SD 3.5 Large", "speed": "~10s"},
        ]

    def default_model(self) -> Optional[str]:
        return "black-forest-labs/FLUX-1-schnell"

    def generate(
        self,
        prompt: str,
        aspect_ratio: str = DEFAULT_ASPECT_RATIO,
        *,
        image_url: Optional[str] = None,
        reference_image_urls: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        prompt = (prompt or "").strip()
        aspect = resolve_aspect_ratio(aspect_ratio)

        if not prompt:
            return error_response(error="Prompt is required", provider="deepinfra", aspect_ratio=aspect)

        api_key = os.environ.get("DEEPINFRA_API_KEY")
        if not api_key:
            return error_response(
                error="DEEPINFRA_API_KEY not set",
                error_type="auth_required", provider="deepinfra", aspect_ratio=aspect,
            )

        model = kwargs.get("model") or self.default_model()

        size_map = {"landscape": "1024x768", "square": "1024x1024", "portrait": "768x1024"}
        size = size_map.get(aspect, "1024x1024")
        w, h = size.split("x")

        payload: Dict[str, Any] = {
            "prompt": prompt,
            "width": int(w),
            "height": int(h),
            "num_images": 1,
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        try:
            resp = requests.post(
                f"https://api.deepinfra.com/v1/inference/{model}",
                headers=headers, json=payload, timeout=120,
            )
            resp.raise_for_status()
            result = resp.json()
        except Exception as exc:
            return error_response(
                error=f"DeepInfra request failed: {exc}",
                error_type="api_error", provider="deepinfra",
                model=model, prompt=prompt, aspect_ratio=aspect,
            )

        image_url_result = None
        if isinstance(result, dict):
            images = result.get("images") or result.get("output")
            if isinstance(images, list) and len(images) > 0:
                first = images[0]
                if isinstance(first, dict):
                    image_url_result = first.get("url") or first.get("image")
                elif isinstance(first, str):
                    image_url_result = first

        if not image_url_result:
            return error_response(
                error="No image in response", provider="deepinfra",
                model=model, prompt=prompt, aspect_ratio=aspect,
            )

        try:
            save_dir = kwargs.get("save_dir")
            local_path = save_url_image(image_url_result, prefix=f"deepinfra_{model.split('/')[-1]}", save_dir=save_dir)
        except Exception as exc:
            logger.warning("Could not cache image: %s", exc)
            local_path = image_url_result

        return success_response(
            image=local_path, model=model, prompt=prompt,
            aspect_ratio=aspect, provider="deepinfra",
        )
