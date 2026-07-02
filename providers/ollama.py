"""providers/ollama.py -- Local Ollama provider (last-resort fallback)."""
import os
import requests
from .base import Provider

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")


class OllamaProvider(Provider):
    name = "ollama"

    @property
    def default_model(self):
        return os.getenv("OLLAMA_MODEL", "llama3.2")

    def available(self) -> bool:
        try:
            r = requests.get(OLLAMA_URL + "/api/tags", timeout=2)
            return r.status_code == 200
        except Exception:
            return False

    def _generate(self, prompt, system, model, max_tokens, temperature) -> str:
        if not model or model.startswith(("gpt", "o1", "o3", "gemini")):
            model = self.default_model
        r = requests.post(
            OLLAMA_URL + "/api/generate",
            json={"model": model, "prompt": prompt, "system": system,
                  "stream": False,
                  "options": {"num_predict": max_tokens, "temperature": temperature}},
            timeout=300,
        )
        r.raise_for_status()
        return r.json().get("response", "").strip()
