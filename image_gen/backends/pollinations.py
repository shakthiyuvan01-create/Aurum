"""
Pollinations.ai image generation backend.
Free, no API key needed. Uses FLUX and other models.
"""
from __future__ import annotations

import logging
import os
import time
import urllib.parse
from typing import Any, Dict, List, Optional

import requests

from image_gen.provider import (
    DEFAULT_ASPECT_RATIO,
    ImageGenProvider,
    error_response,
    resolve_aspect_ratio,
    success_response,
)

logger = logging.getLogger(__name__)

_SIZES = {
    "landscape": "1024x768",
    "square": "1024x1024",
    "portrait": "768x1024",
}


class PollinationsProvider(ImageGenProvider):
    """Free image generation via pollinations.ai — no API key required."""

    @property
    def name(self) -> str:
        return "pollinations"

    @property
    def display_name(self) -> str:
        return "Pollinations AI"

    def is_available(self) -> bool:
        return True  # Always available — free service

    def list_models(self) -> List[Dict[str, Any]]:
        return [
            {"id": "flux", "display": "FLUX", "speed": "~10s", "strengths": "Default, good quality"},
            {"id": "turbo", "display": "Turbo", "speed": "~5s", "strengths": "Fastest"},
        ]

    def default_model(self) -> Optional[str]:
        return "flux"

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
            return error_response(error="Prompt is required", provider="pollinations", aspect_ratio=aspect)

        output_dir = kwargs.get("save_dir") or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "uploads"
        )
        os.makedirs(output_dir, exist_ok=True)
        out = os.path.join(output_dir, f"pollinations_{int(time.time())}.png")

        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        size = _SIZES.get(aspect, _SIZES["square"])
        model = kwargs.get("model", "flux")
        seed = kwargs.get("seed", int(time.time()))

        urls = [
            f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}"
            f"?width={size.split('x')[0]}&height={size.split('x')[1]}&nologo=true&seed={seed}&model={model}",
            f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}"
            f"?width={size.split('x')[0]}&height={size.split('x')[1]}&nologo=true&seed={seed}",
            f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}",
        ]

        for attempt, url in enumerate(urls):
            try:
                r = requests.get(url, headers=headers, timeout=120)
                if r.status_code == 429:
                    logger.warning("Pollinations rate-limited (429), retrying in 3s...")
                    time.sleep(3)
                    continue
                if r.status_code == 200 and len(r.content) > 1000:
                    with open(out, "wb") as f:
                        f.write(r.content)
                    return success_response(
                        image=out,
                        model=model,
                        prompt=prompt,
                        aspect_ratio=aspect,
                        provider="pollinations",
                    )
            except Exception as e:
                logger.warning("Pollinations error: %s", e)

        # Last attempt: try without nologo and with different model
        try:
            fallback_url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}"
            r = requests.get(fallback_url, headers=headers, timeout=180)
            if r.status_code == 200 and len(r.content) > 1000:
                with open(out, "wb") as f:
                    f.write(r.content)
                return success_response(
                    image=out, model="default", prompt=prompt,
                    aspect_ratio=aspect, provider="pollinations",
                )
        except Exception as e:
            logger.warning("Pollinations fallback error: %s", e)

        return error_response(
            error="Pollinations rate-limited or unavailable. Try setting OPENAI_API_KEY, FAL_KEY, or DEEPINFRA_API_KEY for more reliable backends.",
            error_type="rate_limited",
            provider="pollinations",
            aspect_ratio=aspect,
        )
