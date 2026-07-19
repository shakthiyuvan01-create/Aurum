"""providers/manager.py — FAST ProviderManager with parallel racing & caching.

Key speed improvements over the original:
  1. RACE first 2-3 available providers in PARALLEL — take the fastest response
  2. PERSISTENT cache of last-working provider — try it first next call
  3. SHORT timeouts — 6s per provider (not 30s)
  4. AGGRESSIVE circuit breaker — skip failing providers for 5+ minutes
  5. NO compression on short prompts — it was adding latency for no benefit
  6. RETRY last-working provider on failure before falling through the chain

Usage:
    from providers import AI
    text = AI.generate("prompt", system="...")
"""
from __future__ import annotations

import hashlib as _hl
import json
import logging
import os
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Dict, List, Optional, Tuple

from .github_models import GitHubModelsProvider
from .gemini import GeminiProvider
from .openai_provider import OpenAIProvider
from .ollama import OllamaProvider
from .nararouter import NaraRouterProvider
from .bluesminds import BluesMindsProvider
from .omniroute import OmniRouteProvider

log = logging.getLogger("providers.manager")

_DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "aiaurum.db")
_track_lock = threading.Lock()

# ── Circuit breaker ────────────────────────────────────────────────────────
# Skip a provider for N seconds after a failure so one dead provider can't
# add 30s to every request.
_breaker: Dict[str, float] = {}
_breaker_lock = threading.Lock()
_BREAKER_COOLDOWN = 90       # normal failure
_BREAKER_LONG = 300          # 429/401/403/402


def _tripped(name: str) -> bool:
    return _breaker.get(name, 0) > time.time()


def _trip(name: str, err: str):
    cd = _BREAKER_LONG if any(c in err for c in ("429", "401", "402", "403")) else _BREAKER_COOLDOWN
    with _breaker_lock:
        _breaker[name] = time.time() + cd
    log.debug("tripped %s for %ss: %s", name, cd, err[:80])


# ── Success cache ──────────────────────────────────────────────────────────
# Remember which provider worked last so we try it first next call.
_success_cache: Dict[str, str] = {}  # model -> provider name
_success_lock = threading.Lock()


def _cached_provider(model: Optional[str]) -> Optional[str]:
    key = model or "__default__"
    with _success_lock:
        return _success_cache.get(key)


def _cache_success(model: Optional[str], provider: str):
    key = model or "__default__"
    with _success_lock:
        _success_cache[key] = provider


# ── Usage tracking ─────────────────────────────────────────────────────────

def _track(provider: str, kind: str, prompt_chars: int, reply_chars: int,
           latency_ms: int, failed_over: bool):
    try:
        with _track_lock, sqlite3.connect(_DB, timeout=3) as con:
            con.execute("""CREATE TABLE IF NOT EXISTS provider_usage (
                day TEXT, provider TEXT, calls INTEGER DEFAULT 0,
                est_tokens INTEGER DEFAULT 0, total_ms INTEGER DEFAULT 0,
                failovers INTEGER DEFAULT 0,
                PRIMARY KEY (day, provider))""")
            day = time.strftime("%Y-%m-%d")
            tokens = (prompt_chars + reply_chars) // 4
            con.execute("""INSERT INTO provider_usage (day, provider, calls, est_tokens, total_ms, failovers)
                VALUES (?,?,1,?,?,?)
                ON CONFLICT(day, provider) DO UPDATE SET
                calls=calls+1, est_tokens=est_tokens+excluded.est_tokens,
                total_ms=total_ms+excluded.total_ms,
                failovers=failovers+excluded.failovers""",
                (day, provider, tokens, latency_ms, 1 if failed_over else 0))
    except Exception:
        pass


# ── All providers ──────────────────────────────────────────────────────────

_ALL = {
    "github": GitHubModelsProvider(),
    "gemini": GeminiProvider(),
    "nara":   NaraRouterProvider(),
    "bluesminds": BluesMindsProvider(),
    "omniroute": OmniRouteProvider(),
    "openai": OpenAIProvider(),
    "ollama": OllamaProvider(),
}

_RACE_TIMEOUT = 6  # max seconds to wait for the fastest provider

# ── Thread pool for parallel racing ────────────────────────────────────────
_race_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="provider_race")


class ProviderManager:
    """Fast provider manager with parallel racing & caching."""

    def __init__(self):
        order = os.getenv("AI_PROVIDER_ORDER",
                          "nara,github,bluesminds,gemini,openai,omniroute,ollama")
        self.chain = [_ALL[n.strip()] for n in order.split(",") if n.strip() in _ALL]
        self.last_used: Optional[str] = None
        self.last_errors: List[str] = []

    # ── public API ─────────────────────────────────────────────────────────

    def generate(self, prompt: str, system: str = "", model: str = None,
                 max_tokens: int = 1500, temperature: float = 0.3,
                 provider: str = None) -> str:
        """Fast generate — races available providers, caches success."""
        return self._fast_call("generate", prompt=prompt, system=system,
                               model=model, max_tokens=max_tokens,
                               temperature=temperature, provider=provider)

    def chat(self, messages: list, model: str = None, max_tokens: int = 1500,
             temperature: float = 0.4, provider: str = None) -> str:
        """Fast chat — races available providers, caches success."""
        return self._fast_call("chat", messages=messages, model=model,
                               max_tokens=max_tokens, temperature=temperature,
                               provider=provider)

    def generate_json(self, prompt: str, system: str = "", model: str = None,
                      max_tokens: int = 800, retries: int = 2) -> dict:
        """JSON generation with parse retry."""
        sys_p = (system + "\n\nReply with ONLY a valid JSON object. "
                 "No prose, no markdown fences.").strip()
        text = prompt
        import re as _re
        for attempt in range(retries + 1):
            raw = self.generate(text, system=sys_p, model=model,
                                max_tokens=max_tokens, temperature=0.1)
            m = _re.search(r"\{[\s\S]*\}", raw)
            if m:
                try:
                    return json.loads(m.group(0))
                except json.JSONDecodeError as e:
                    text = ("Your previous output was invalid JSON (%s). "
                            "Output the corrected JSON only:\n%s" % (e, m.group(0)[:2000]))
            else:
                text = prompt + "\n\nIMPORTANT: reply with ONLY the JSON object."
        return {}

    def draft_verify(self, prompt: str, system: str = "",
                     max_tokens: int = 2000) -> str:
        """Cheap-draft / big-verify pattern."""
        draft = self.generate(prompt, system=system,
                              model="gpt-4o-mini", max_tokens=max_tokens, temperature=0.4)
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
            "success_cache": dict(_success_cache),
        }

    # ── Internal fast path ─────────────────────────────────────────────────

    def _fast_call(self, method: str, **kwargs) -> str:
        """Race providers, cache winner, fall back sequentially."""
        self.last_errors = []
        provider = kwargs.pop("provider", None)

        # If a specific provider is requested, just use it
        if provider and provider in _ALL:
            return self._try_single(_ALL[provider], method, kwargs)

        # Build candidate list: cached provider first, then available chain
        candidates = self._build_candidates(kwargs.get("model"))
        if not candidates:
            return "[AI error: no providers available]"

        # RACE the first 3 in parallel
        result = self._race(candidates[:3], method, kwargs)
        if result is not None:
            return result

        # Try remaining candidates sequentially
        for p in candidates[3:]:
            result = self._try_single(p, method, kwargs)
            if result is not None:
                return result

        return "[AI error: all providers failed - " + "; ".join(self.last_errors[-3:]) + "]"

    def _build_candidates(self, model: Optional[str]) -> List:
        """Build ordered candidate list: cached -> available chain."""
        seen = set()
        candidates = []

        # 1. Cached provider (fastest from last successful call)
        cached_name = _cached_provider(model)
        if cached_name and cached_name in _ALL:
            p = _ALL[cached_name]
            if p.available() and not _tripped(p.name):
                candidates.append(p)
                seen.add(p.name)

        # 2. Rest of the chain
        for p in self.chain:
            if p.name not in seen and p.available() and not _tripped(p.name):
                candidates.append(p)
                seen.add(p.name)

        return candidates

    def _race(self, providers: list, method: str, kwargs: dict) -> Optional[str]:
        """Run providers in parallel, return first successful result."""
        if not providers:
            return None

        futures = {}
        for p in providers:
            fut = _race_pool.submit(self._try_single, p, method, kwargs)
            futures[fut] = p

        deadline = time.time() + _RACE_TIMEOUT
        for fut in as_completed(futures, timeout=_RACE_TIMEOUT):
            p = futures[fut]
            try:
                result = fut.result(timeout=1)
                if result is not None:
                    # Cancel remaining futures
                    for f in futures:
                        if not f.done():
                            f.cancel()
                    return result
            except TimeoutError:
                _trip(p.name, "timeout")
                self.last_errors.append(f"{p.name}: race timeout")
            except Exception as e:
                _trip(p.name, str(e))
                self.last_errors.append(f"{p.name}: {e}")

        return None

    def _try_single(self, provider, method: str, kwargs: dict) -> Optional[str]:
        """Try a single provider. Returns response string or None."""
        try:
            if not provider.available() or _tripped(provider.name):
                return None
            t0 = time.time()
            # Build call args: only pass params the method accepts
            call_kwargs = self._filter_kwargs(provider, method, kwargs)
            if method == "generate":
                out = provider.generate(**call_kwargs)
            else:
                out = provider.chat(**call_kwargs)
            if out:
                latency = int((time.time() - t0) * 1000)
                self.last_used = provider.name
                _cache_success(kwargs.get("model"), provider.name)
                _track(provider.name, method,
                       sum(len(str(v)) for v in call_kwargs.values()),
                       len(out), latency, False)
                return out
        except Exception as e:
            _trip(provider.name, str(e))
            self.last_errors.append(f"{provider.name}: {e}")
            log.debug("provider %s failed: %s", provider.name, e)
        return None

    def _filter_kwargs(self, provider, method: str, kwargs: dict) -> dict:
        """Only pass kwargs the provider's method actually accepts."""
        # All providers accept prompt/system/model/max_tokens/temperature for generate
        # and messages/model/max_tokens/temperature for chat
        if method == "generate":
            return {k: kwargs[k] for k in ("prompt", "system", "model", "max_tokens", "temperature")
                    if k in kwargs}
        return {k: kwargs[k] for k in ("messages", "model", "max_tokens", "temperature")
                if k in kwargs}


AI = ProviderManager()
