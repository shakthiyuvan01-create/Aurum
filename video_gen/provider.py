"""
Video Generation Provider ABC — pluggable backend for video generation.
Port of Hermes' video_gen provider pattern adapted for Aurum.
"""
from __future__ import annotations

import abc
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class VideoGenProvider(abc.ABC):
    """Abstract base class for video generation backends."""

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Short identifier, lowercase, no spaces."""

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

    @abc.abstractmethod
    def generate(
        self,
        prompt: str,
        *,
        duration: int = 5,
        negative_prompt: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Generate a video from a text prompt."""
