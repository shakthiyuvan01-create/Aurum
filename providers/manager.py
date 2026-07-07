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
import sqlite3
import threading
import time

from .github_models import GitHubModelsProvider
from .gemini import GeminiProvider
from .openai_provider import OpenAIProvider
from .ollama import OllamaProvider
from .nararouter import NaraRouterProvider
from .bluesminds import BluesMindsProvider

log = logging.getLogger("providers.manager")

_DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "aiaurum.db")
_track_lock = threading.Lock()

# Circuit breaker: after a failure, skip a provider for a cooldown so one dead
# provider (bad key, 503, 429) can't add 30s to every request.
_breaker = {}   # provider name -> unix time to retry after
_BREAKER_COOLDOWN = 90


def _tripped(name: str) -> bool:
    return _breaker.get(name, 0) > time.time()


def _trip(name: str, err: str):
    # rate-limit and auth/plan errors deserve a longer cooldown
    cd = 300 if any(c in err for c in ("429", "401", "402", "403")) else _BREAKER_COOLDOWN
    _breaker[name] = time.time() + cd


def _track(provider: str, kind: str, prompt_chars: int, reply_chars: int,
           latency_ms: int, failed_over: bool):
    """Persist usage: calls, est. tokens, latency, failovers per provider/day."""
    try:
        with _track_lock, sqlite3.connect(_DB, timeout=5) as con:
            con.execute("""CREATE TABLE IF NOT EXISTS provider_usage (
                day TEXT, provider TEXT, calls INTEGER DEFAULT 0,
                est_tokens INTEGER DEFAULT 0, total_ms INTEGER DEFAULT 0,
                failovers INTEGER DEFAULT 0,
                PRIMARY KEY (day, provider))""")
            day = time.strftime("%Y-%m-%d")
            tokens = (prompt_chars + reply_chars) // 4  # rough chars->tokens
            con.execute("""INSERT INTO provider_usage (day, provider, calls, est_tokens, total_ms, failovers)
                VALUES (?,?,1,?,?,?)
                ON CONFLICT(day, provider) DO UPDATE SET
                calls=calls+1, est_tokens=est_tokens+excluded.est_tokens,
                total_ms=total_ms+excluded.total_ms,
                failovers=failovers+excluded.failovers""",
                (day, provider, tokens, latency_ms, 1 if failed_over else 0))
    except Exception as e:
        log.debug("usage track failed: %s", e)

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
                          "nara,github,bluesminds,gemini,openai,ollama")
        self.chain = [_ALL[n.strip()] for n in order.split(",") if n.strip() in _ALL]
        self.last_used = None
        self.last_errors = []

    def generate(self, prompt: str, system: str = "", model: str = None,
                 max_tokens: int = 1500, temperature: float = 0.3,
                 provider: str = None) -> str:
        """Try providers in order until one succeeds."""
        self.last_errors = []
        chain = [_ALL[provider]] if provider in _ALL else self.chain
        failed_over = False
        for p in chain:
            try:
                if not p.available() or _tripped(p.name):
                    continue
                t0 = time.time()
                out = p.generate(prompt, system=system, model=model,
                                 max_tokens=max_tokens, temperature=temperature)
                if out:
                    self.last_used = p.name
                    _track(p.name, "generate", len(prompt) + len(system or ""),
                           len(out), int((time.time() - t0) * 1000), failed_over)
                    return out
            except Exception as e:
                failed_over = True
                _trip(p.name, str(e))
                self.last_errors.append("%s: %s" % (p.name, e))
                log.warning("provider %s failed: %s", p.name, e)
        return "[AI error: all providers failed - " + "; ".join(self.last_errors[-3:]) + "]"

    def chat(self, messages: list, model: str = None, max_tokens: int = 1500,
             temperature: float = 0.4, provider: str = None) -> str:
        """Multi-turn chat through the fallback chain."""
        self.last_errors = []
        chain = [_ALL[provider]] if provider in _ALL else self.chain
        failed_over = False
        for p in chain:
            try:
                if not p.available() or _tripped(p.name):
                    continue
                t0 = time.time()
                out = p.chat(messages, model=model, max_tokens=max_tokens,
                             temperature=temperature)
                if out:
                    self.last_used = p.name
                    _track(p.name, "chat",
                           sum(len(str(m.get("content", ""))) for m in messages),
                           len(out), int((time.time() - t0) * 1000), failed_over)
                    return out
            except Exception as e:
                failed_over = True
                _trip(p.name, str(e))
                self.last_errors.append("%s: %s" % (p.name, e))
                log.warning("provider %s chat failed: %s", p.name, e)
        return "[AI error: all providers failed - " + "; ".join(self.last_errors[-3:]) + "]"

    def generate_json(self, prompt: str, system: str = "", model: str = None,
                      max_tokens: int = 800, retries: int = 2) -> dict:
        """Schema-disciplined generation: always returns a parsed dict or {}.
        Retries with an explicit repair instruction on parse failure."""
        import json as _json, re as _re
        sys_p = (system + "\n\nReply with ONLY a valid JSON object. "
                 "No prose, no markdown fences.").strip()
        text = prompt
        for attempt in range(retries + 1):
            raw = self.generate(text, system=sys_p, model=model,
                                max_tokens=max_tokens, temperature=0.1)
            m = _re.search(r"\{[\s\S]*\}", raw)
            if m:
                try:
                    return _json.loads(m.group(0))
                except _json.JSONDecodeError as e:
                    text = ("Your previous output was invalid JSON (%s). "
                            "Output the corrected JSON only:\n%s"
                            % (e, m.group(0)[:2000]))
            else:
                text = prompt + "\n\nIMPORTANT: reply with ONLY the JSON object."
        return {}

    def draft_verify(self, prompt: str, system: str = "",
                     max_tokens: int = 2000) -> str:
        """Cheap-draft / big-verify: a small model writes the draft, the big
        model only reviews and patches it. 3-5x cheaper long outputs."""
        draft = self.generate(prompt, system=system,
                              model="gpt-4o-mini", max_tokens=max_tokens,
                              temperature=0.4)
        if draft.startswith("[AI error"):
            return self.generate(prompt, system=system, model="gpt-4o",
                                 max_tokens=max_tokens, temperature=0.3)
        fixed = self.generate(
            "Review this draft against the original request. Fix factual "
            "errors, calculation mistakes and gaps. Output the corrected "
            "final version ONLY (no commentary).\n\nREQUEST:\n%s\n\nDRAFT:\n%s"
            % (prompt[:3000], draft[:12000]),
            system=system, model="gpt-4o", max_tokens=max_tokens, temperature=0.2)
        return fixed if not fixed.startswith("[AI error") else draft

    def status(self) -> dict:
        return {
            "chain": [p.name for p in self.chain],
            "available": {p.name: p.available() for p in self.chain},
            "circuit_open": {n: round(t - time.time()) for n, t in _breaker.items()
                             if t > time.time()},
            "last_used": self.last_used,
            "last_errors": self.last_errors,
        }


AI = ProviderManager()
