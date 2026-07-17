"""providers/nararouter.py -- NaraRouter gateway (OpenAI-compatible).

Free-tier LLM gateway at https://router.bynara.id/v1.
Env: NARA_API_KEY (required), NARA_MODEL (default mistral-large),
     NARA_BASE_URL (default https://router.bynara.id/v1).
"""
import os
import requests
from .base import Provider


def _base_url():
    return os.getenv("NARA_BASE_URL", "https://router.bynara.id/v1").rstrip("/")


class NaraRouterProvider(Provider):
    name = "nara"

    @property
    def default_model(self):
        return os.getenv("NARA_MODEL", "mistral-large")

    def available(self) -> bool:
        return bool(os.getenv("NARA_API_KEY", ""))

    def _map_model(self, model):
        # GPT/Gemini model names do not exist on this gateway -- use our default
        if not model or model.startswith(("gpt", "o1", "o3", "gemini")):
            return self.default_model
        return model

    def _generate(self, prompt, system, model, max_tokens, temperature) -> str:
        msgs = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.append({"role": "user", "content": prompt})
        return self._post(msgs, model, max_tokens, temperature)

    def chat(self, messages, model=None, max_tokens=1500, temperature=0.4):
        return self._post(messages, model, max_tokens, temperature)

    def _post(self, messages, model, max_tokens, temperature) -> str:
        r = requests.post(
            _base_url() + "/chat/completions",
            headers={"Authorization": "Bearer " + os.getenv("NARA_API_KEY", ""),
                     "Content-Type": "application/json"},
            json={"model": self._map_model(model), "messages": messages,
                  "max_tokens": max_tokens, "temperature": temperature},
            timeout=8,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()
