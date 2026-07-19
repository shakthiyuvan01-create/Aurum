"""
FAL.ai image generation backend.
Wraps FAL's REST API for FLUX, Stable Diffusion, and other models.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

from image_gen.provider import (
    DEFAULT_ASPECT_RATIO,
    ImageGenProvider,
    error_response,
    resolve_aspect_ratio,
    save_url_image,
    success_response,
)

logger = logging.getLogger(__name__)

FAL_MODELS: Dict[str, Dict[str, Any]] = {
    "flux-pro": {
        "display": "FLUX 1.1 Pro",
        "speed": "~10s",
        "strengths": "Best quality, photorealistic",
        "price": "$0.040",
    },
    "flux-dev": {
        "display": "FLUX Dev",
        "speed": "~8s",
        "strengths": "Fast, good quality",
        "price": "$0.025",
    },
    "flux-schnell": {
        "display": "FLUX Schnell",
        "speed": "~3s",
        "strengths": "Ultra-fast",
        "price": "$0.010",
    },
    "stable-diffusion-3.5": {
        "display": "SD 3.5 Large",
        "speed": "~12s",
        "strengths": "Versatile, good typography",
        "price": "$0.035",
    },
}

DEFAULT_MODEL = "flux-dev"
FAL_API_BASE = "https://fal.run"


class FalImageProvider(ImageGenProvider):
    """FAL.ai image generation backend."""

    @property
    def name(self) -> str:
        return "fal"

    @property
    def display_name(self) -> str:
        return "FAL.ai"

    def is_available(self) -> bool:
        return bool(os.environ.get("FAL_KEY"))

    def list_models(self) -> List[Dict[str, Any]]:
        return [
            {"id": mid, "display": meta["display"], "speed": meta["speed"],
             "strengths": meta["strengths"], "price": meta["price"]}
            for mid, meta in FAL_MODELS.items()
        ]

    def default_model(self) -> Optional[str]:
        return DEFAULT_MODEL

    def capabilities(self) -> Dict[str, Any]:
        return {"modalities": ["text", "image"], "max_reference_images": 1}

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
            return error_response(error="Prompt is required", provider="fal", aspect_ratio=aspect)

        api_key = os.environ.get("FAL_KEY")
        if not api_key:
            return error_response(
                error="FAL_KEY not set",
                error_type="auth_required", provider="fal", aspect_ratio=aspect,
            )

        model_id = kwargs.get("model") or DEFAULT_MODEL
        if model_id not in FAL_MODELS:
            model_id = DEFAULT_MODEL

        # Map aspect ratio to FAL sizes
        size_map = {"landscape": "1024x768", "square": "1024x1024", "portrait": "768x1024"}
        size = size_map.get(aspect, "1024x1024")
        w, h = size.split("x")

        import requests
        headers = {
            "Authorization": f"Key {api_key}",
            "Content-Type": "application/json",
        }

        endpoint_map = {
            "flux-pro": f"{FAL_API_BASE}/fal-ai/flux-pro/v1.1",
            "flux-dev": f"{FAL_API_BASE}/fal-ai/flux/dev",
            "flux-schnell": f"{FAL_API_BASE}/fal-ai/flux/schnell",
            "stable-diffusion-3.5": f"{FAL_API_BASE}/fal-ai/stable-diffusion-v3-5",
        }

        endpoint = endpoint_map.get(model_id, endpoint_map[DEFAULT_MODEL])
        payload: Dict[str, Any] = {
            "prompt": prompt,
            "image_size": {"width": int(w), "height": int(h)},
            "num_inference_steps": kwargs.get("num_inference_steps", 28),
            "guidance_scale": kwargs.get("guidance_scale", 7.0),
        }

        if image_url:
            payload["image_url"] = image_url

        try:
            resp = requests.post(endpoint, headers=headers, json=payload, timeout=120)
            resp.raise_for_status()
            result = resp.json()
        except Exception as exc:
            return error_response(
                error=f"FAL request failed: {exc}",
                error_type="api_error", provider="fal",
                model=model_id, prompt=prompt, aspect_ratio=aspect,
            )

        image_url_result = None
        if isinstance(result, dict):
            for key in ("image", "images", "output", "result"):
                val = result.get(key)
                if isinstance(val, str) and val.startswith(("http://", "https://")):
                    image_url_result = val
                    break
                if isinstance(val, list) and len(val) > 0:
                    first = val[0]
                    if isinstance(first, dict):
                        image_url_result = first.get("url") or first.get("image")
                    elif isinstance(first, str):
                        image_url_result = first
                    if image_url_result:
                        break

        if not image_url_result:
            return error_response(
                error="No image URL in FAL response",
                error_type="empty_response", provider="fal",
                model=model_id, prompt=prompt, aspect_ratio=aspect,
            )

        try:
            save_dir = kwargs.get("save_dir")
            local_path = save_url_image(image_url_result, prefix=f"fal_{model_id}", save_dir=save_dir)
        except Exception as exc:
            logger.warning("Could not cache FAL image: %s", exc)
            local_path = image_url_result

        return success_response(
            image=local_path, model=model_id, prompt=prompt,
            aspect_ratio=aspect, provider="fal",
        )
