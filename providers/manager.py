"""providers/manager.py -- ProviderManager: one place to call any AI.

Usage everywhere in the codebase:

    from providers import AI
    text = AI.generate("prompt", system="...", model="gpt-4o", max_tokens=800)

Fallback chain (env AI_PROVIDER_ORDER, default: github,gemini,openai,ollama).
Never raises -- returns an "[AI error: ...]" string on total failure, matching
the error-string convention the tools already use.
"""
import os
import logging

from .github_models import GitHubModelsProvider
from .gemini import GeminiProvider
from .openai_provider import OpenAIProvider
from .ollama import OllamaProvider
from .nararouter import NaraRouterProvider
from .bluesminds import BluesMindsProvider

log = logging.getLogger("providers.manager")

_ALL = {
    "github": GitHubModelsProvider(),
    "gemini": GeminiProvider(),
    "nara":   NaraRouterProvider(),
    "bluesminds": BluesMindsProvider(),
    "openai": OpenAIProvider(),
    "ollama": OllamaProvider(),
}


class ProviderManager:
    def __init__(self):
        order = os.getenv("AI_PROVIDER_ORDER",
                          "github,nara,bluesminds,ollama,gemini,openai")
        self.chain = [_ALL[n.strip()] for n in order.split(",") if n.strip() in _ALL]
        self.last_used = None
        self.last_errors = []

    def generate(self, prompt: str, system: str = "", model: str = None,
                 max_tokens: int = 1500, temperature: float = 0.3,
                 provider: str = None) -> str:
        """Try providers in order until one succeeds."""
        self.last_errors = []
        chain = [_ALL[provider]] if provider in _ALL else self.chain
        for p in chain:
            try:
                if not p.available():
                    continue
                out = p.generate(prompt, system=system, model=model,
                                 max_tokens=max_tokens, temperature=temperature)
                if out:
                    self.last_used = p.name
                    return out
            except Exception as e:
                self.last_errors.append("%s: %s" % (p.name, e))
                log.warning("provider %s failed: %s", p.name, e)
        return "[AI error: all providers failed - " + "; ".join(self.last_errors[-3:]) + "]"

    def chat(self, messages: list, model: str = None, max_tokens: int = 1500,
             temperature: float = 0.4, provider: str = None) -> str:
        """Multi-turn chat through the fallback chain."""
        self.last_errors = []
        chain = [_ALL[provider]] if provider in _ALL else self.chain
        for p in chain:
            try:
                if not p.available():
                    continue
                out = p.chat(messages, model=model, max_tokens=max_tokens,
                             temperature=temperature)
                if out:
                    self.last_used = p.name
                    return out
            except Exception as e:
                self.last_errors.append("%s: %s" % (p.name, e))
                log.warning("provider %s chat failed: %s", p.name, e)
        return "[AI error: all providers failed - " + "; ".join(self.last_errors[-3:]) + "]"

    def status(self) -> dict:
        return {
            "chain": [p.name for p in self.chain],
            "available": {p.name: p.available() for p in self.chain},
            "last_used": self.last_used,
            "last_errors": self.last_errors,
        }


AI = ProviderManager()
