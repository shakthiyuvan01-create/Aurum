"""FAL.ai video generation backend."""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

import requests

from video_gen.provider import VideoGenProvider

logger = logging.getLogger(__name__)

FAL_MODELS = {
    "kling-video": {"display": "KLING Video", "speed": "~60s"},
    "mochi-1": {"display": "Mochi 1", "speed": "~120s"},
    "luma-dream-machine": {"display": "Luma Dream Machine", "speed": "~90s"},
}

FAL_API_BASE = "https://fal.run"


class FalVideoProvider(VideoGenProvider):
    """FAL.ai video generation backend."""

    @property
    def name(self) -> str:
        return "fal"

    @property
    def display_name(self) -> str:
        return "FAL.ai Video"

    def is_available(self) -> bool:
        return bool(os.environ.get("FAL_KEY"))

    def list_models(self) -> List[Dict[str, Any]]:
        return [{"id": k, **v} for k, v in FAL_MODELS.items()]

    def default_model(self) -> Optional[str]:
        return "kling-video"

    def generate(
        self,
        prompt: str,
        *,
        duration: int = 5,
        negative_prompt: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        api_key = os.environ.get("FAL_KEY")
        if not api_key:
            return {"success": False, "error": "FAL_KEY not set", "video": None}

        model = kwargs.get("model") or "kling-video"
        endpoint = f"{FAL_API_BASE}/fal-ai/{model}"

        payload = {"prompt": prompt, "duration": duration}
        if negative_prompt:
            payload["negative_prompt"] = negative_prompt

        headers = {"Authorization": f"Key {api_key}", "Content-Type": "application/json"}

        try:
            resp = requests.post(endpoint, headers=headers, json=payload, timeout=300)
            resp.raise_for_status()
            result = resp.json()
        except Exception as exc:
            return {"success": False, "error": str(exc), "video": None}

        video_url = None
        if isinstance(result, dict):
            video_url = result.get("video", {}).get("url") or result.get("url") or result.get("output")

        if video_url:
            return {"success": True, "video": video_url, "model": model, "provider": "fal"}
        return {"success": False, "error": "No video URL in response", "video": None}
