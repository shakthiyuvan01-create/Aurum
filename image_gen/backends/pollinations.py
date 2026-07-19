"""
Pollinations.ai image generation backend — FAST version.
Races URLs in parallel with 15s timeout, returns first success.
"""
from __future__ import annotations

import logging
import os
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
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

_SIZES = {"landscape": "1024x768", "square": "1024x1024", "portrait": "768x1024"}
_RACE_TIMEOUT = 18  # max seconds to wait for the fastest URL


class PollinationsProvider(ImageGenProvider):
    """Free image generation via pollinations.ai — no API key required."""

    @property
    def name(self) -> str:
        return "pollinations"

    @property
    def display_name(self) -> str:
        return "Pollinations AI"

    def is_available(self) -> bool:
        return True

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

        # Build all URLs
        quoted = urllib.parse.quote(prompt)
        urls = [
            f"https://image.pollinations.ai/prompt/{quoted}?width={size.split('x')[0]}&height={size.split('x')[1]}&nologo=true&seed={seed}&model={model}",
            f"https://image.pollinations.ai/prompt/{quoted}?width={size.split('x')[0]}&height={size.split('x')[1]}&nologo=true&seed={seed}",
            f"https://image.pollinations.ai/prompt/{quoted}",
            f"https://image.pollinations.ai/prompt/{quoted}?model=flux&nologo=true",
        ]

        # Race all URLs in parallel
        with ThreadPoolExecutor(max_workers=4) as pool:
            fut_map = {pool.submit(_fetch_url, url, headers): url for url in urls}
            try:
                for fut in as_completed(fut_map, timeout=_RACE_TIMEOUT):
                    data = fut.result(timeout=2)
                    if data is not None:
                        # Cancel remaining
                        for f in fut_map:
                            if not f.done():
                                f.cancel()
                        with open(out, "wb") as f:
                            f.write(data)
                        return success_response(
                            image=out, model=model, prompt=prompt,
                            aspect_ratio=aspect, provider="pollinations",
                        )
            except TimeoutError:
                pass

        return error_response(
            error=("Image generation timed out. Pollinations may be rate-limited. "
                   "Try setting OPENAI_API_KEY for a faster backend."),
            error_type="timeout", provider="pollinations", aspect_ratio=aspect,
        )


def _fetch_url(url: str, headers: dict, timeout: int = 15) -> Optional[bytes]:
    """Fetch a URL, return bytes if valid image, None otherwise."""
    try:
        r = requests.get(url, headers=headers, timeout=timeout)
        if r.status_code == 200 and len(r.content) > 1000:
            return r.content
        if r.status_code == 429:
            logger.debug("Pollinations 429 for %s", url[:60])
    except Exception as e:
        logger.debug("Fetch error for %s: %s", url[:60], e)
    return None
