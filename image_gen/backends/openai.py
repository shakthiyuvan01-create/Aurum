"""
OpenAI image generation backend.
Supports gpt-image-2 and DALL-E models with text-to-image & editing.
"""
from __future__ import annotations

import io
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

from image_gen.provider import (
    DEFAULT_ASPECT_RATIO,
    ImageGenProvider,
    error_response,
    normalize_reference_images,
    resolve_aspect_ratio,
    save_b64_image,
    success_response,
)

logger = logging.getLogger(__name__)

_MODELS: Dict[str, Dict[str, Any]] = {
    "gpt-image-2-low": {
        "display": "GPT Image 2 (Low)",
        "speed": "~15s",
        "strengths": "Fast iteration, lowest cost",
        "quality": "low",
    },
    "gpt-image-2-medium": {
        "display": "GPT Image 2 (Medium)",
        "speed": "~40s",
        "strengths": "Balanced — default",
        "quality": "medium",
    },
    "gpt-image-2-high": {
        "display": "GPT Image 2 (High)",
        "speed": "~2min",
        "strengths": "Highest fidelity, strongest prompt adherence",
        "quality": "high",
    },
    "dall-e-3": {
        "display": "DALL-E 3",
        "speed": "~30s",
        "strengths": "High quality, creative",
        "quality": "standard",
    },
}

DEFAULT_MODEL = "gpt-image-2-medium"
API_MODEL_MAP = {
    "gpt-image-2-low": "gpt-image-2",
    "gpt-image-2-medium": "gpt-image-2",
    "gpt-image-2-high": "gpt-image-2",
    "dall-e-3": "dall-e-3",
}

_SIZES = {
    "landscape": "1536x1024",
    "square": "1024x1024",
    "portrait": "1024x1536",
}


class OpenAIImageProvider(ImageGenProvider):
    """OpenAI image generation backend — gpt-image-2 & DALL-E."""

    @property
    def name(self) -> str:
        return "openai"

    @property
    def display_name(self) -> str:
        return "OpenAI"

    def is_available(self) -> bool:
        key = os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENAI_KEY")
        if not key:
            return False
        try:
            import openai  # noqa: F401
            return True
        except ImportError:
            return False

    def list_models(self) -> List[Dict[str, Any]]:
        return [
            {"id": mid, "display": meta["display"], "speed": meta["speed"],
             "strengths": meta["strengths"], "price": "varies"}
            for mid, meta in _MODELS.items()
        ]

    def default_model(self) -> Optional[str]:
        return DEFAULT_MODEL

    def capabilities(self) -> Dict[str, Any]:
        return {"modalities": ["text", "image"], "max_reference_images": 16}

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
            return error_response(error="Prompt is required", provider="openai", aspect_ratio=aspect)

        api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENAI_KEY")
        if not api_key:
            return error_response(
                error="OPENAI_API_KEY not set",
                error_type="auth_required", provider="openai", aspect_ratio=aspect,
            )

        try:
            import openai
        except ImportError:
            return error_response(
                error="openai package not installed (pip install openai)",
                error_type="missing_dependency", provider="openai", aspect_ratio=aspect,
            )

        # Model selection
        model_id = kwargs.get("model") or DEFAULT_MODEL
        if model_id not in _MODELS:
            model_id = DEFAULT_MODEL
        meta = _MODELS[model_id]
        api_model = API_MODEL_MAP.get(model_id, "gpt-image-2")
        size = _SIZES.get(aspect, _SIZES["square"])

        # Collect source images for editing
        sources: List[str] = []
        if isinstance(image_url, str) and image_url.strip():
            sources.append(image_url.strip())
        for ref in (normalize_reference_images(reference_image_urls) or []):
            sources.append(ref)
        sources = sources[:16]
        is_edit = bool(sources)
        modality = "image" if is_edit else "text"

        client = openai.OpenAI(api_key=api_key)

        if is_edit:
            try:
                files = []
                for ref in sources:
                    if ref.lower().startswith(("http://", "https://")):
                        import requests
                        resp = requests.get(ref, timeout=60)
                        resp.raise_for_status()
                        data = resp.content
                    elif ref.lower().startswith("data:"):
                        import base64
                        _, _, b64 = ref.partition(",")
                        data = base64.b64decode(b64)
                    else:
                        with open(ref, "rb") as fh:
                            data = fh.read()
                    bio = io.BytesIO(data)
                    bio.name = "image.png"
                    files.append(bio)
            except Exception as exc:
                return error_response(
                    error=f"Could not load source image: {exc}",
                    error_type="io_error", provider="openai",
                    model=model_id, prompt=prompt, aspect_ratio=aspect,
                )

            try:
                response = client.images.edit(
                    model=api_model, image=files[0] if len(files) == 1 else files,
                    prompt=prompt, size=size, quality=meta.get("quality", "standard"), n=1,
                )
            except Exception as exc:
                return error_response(
                    error=f"OpenAI edit failed: {exc}",
                    error_type="api_error", provider="openai",
                    model=model_id, prompt=prompt, aspect_ratio=aspect,
                )
        else:
            payload = {
                "model": api_model, "prompt": prompt, "size": size,
                "n": 1,
            }
            if api_model == "gpt-image-2":
                payload["quality"] = meta.get("quality", "medium")
            try:
                response = client.images.generate(**payload)
            except Exception as exc:
                return error_response(
                    error=f"OpenAI generation failed: {exc}",
                    error_type="api_error", provider="openai",
                    model=model_id, prompt=prompt, aspect_ratio=aspect,
                )

        data = getattr(response, "data", None) or []
        if not data:
            return error_response(
                error="OpenAI returned no image data",
                error_type="empty_response", provider="openai",
                model=model_id, prompt=prompt, aspect_ratio=aspect,
            )

        first = data[0]
        b64 = getattr(first, "b64_json", None)
        url = getattr(first, "url", None)
        revised_prompt = getattr(first, "revised_prompt", None)

        save_dir = kwargs.get("save_dir")
        if b64:
            image_ref = save_b64_image(b64, prefix=f"openai_{model_id}", save_dir=save_dir)
        elif url:
            from image_gen.provider import save_url_image as _sui
            image_ref = _sui(url, prefix=f"openai_{model_id}", save_dir=save_dir)
        else:
            return error_response(
                error="No image in response", provider="openai",
                model=model_id, prompt=prompt, aspect_ratio=aspect,
            )

        extra = {"size": size, "quality": meta.get("quality", "standard")}
        if revised_prompt:
            extra["revised_prompt"] = revised_prompt

        return success_response(
            image=image_ref, model=model_id, prompt=prompt,
            aspect_ratio=aspect, provider="openai", modality=modality, extra=extra,
        )
