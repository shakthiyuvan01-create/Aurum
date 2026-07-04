"""providers -- unified AI provider layer.

    from providers import AI
    AI.generate("prompt", system="...", model="gpt-4o")
"""
from .manager import AI, ProviderManager

__all__ = ["AI", "ProviderManager"]
