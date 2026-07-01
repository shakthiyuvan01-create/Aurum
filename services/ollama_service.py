"""
services/ollama_service.py — Local Ollama model integration.
Auto-detects running models, streams chat, falls back gracefully.
"""
import json
import logging
import os

log = logging.getLogger("services.ollama")

OLLAMA_BASE = os.getenv("OLLAMA_URL", "http://localhost:11434")


def is_available() -> bool:
    """Check if Ollama is running and has at least one model."""
    try:
        import requests
        r = requests.get(f"{OLLAMA_BASE}/api/tags", timeout=2)
        if r.status_code == 200:
            models = r.json().get("models", [])
            return len(models) > 0
        return False
    except Exception:
        return False


def list_models() -> list[str]:
    try:
        import requests
        r = requests.get(f"{OLLAMA_BASE}/api/tags", timeout=3)
        if r.status_code == 200:
            return [m["name"] for m in r.json().get("models", [])]
    except Exception:
        pass
    return []


def chat(prompt: str, model: str = None, system: str = "") -> str:
    """Single-turn chat. Returns response text or empty string on failure."""
    model = model or os.getenv("OLLAMA_MODEL", "llama3.2")
    try:
        import requests
        payload: dict = {"model": model, "prompt": prompt, "stream": False}
        if system:
            payload["system"] = system
        r = requests.post(f"{OLLAMA_BASE}/api/generate", json=payload, timeout=60)
        if r.status_code == 200:
            return r.json().get("response", "").strip()
        return ""
    except Exception as e:
        log.debug("Ollama chat failed: %s", e)
        return ""


def stream_chat(prompt: str, model: str = None, system: str = ""):
    """Generator yielding text chunks from streaming Ollama response."""
    model = model or os.getenv("OLLAMA_MODEL", "llama3.2")
    try:
        import requests
        payload: dict = {"model": model, "prompt": prompt, "stream": True}
        if system:
            payload["system"] = system
        with requests.post(f"{OLLAMA_BASE}/api/generate", json=payload,
                           stream=True, timeout=120) as r:
            for line in r.iter_lines():
                if not line:
                    continue
                data = json.loads(line)
                token = data.get("response", "")
                if token:
                    yield token
                if data.get("done"):
                    break
    except Exception as e:
        log.warning("Ollama stream failed: %s", e)
        yield ""
