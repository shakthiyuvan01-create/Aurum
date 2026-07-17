"""providers/bluesminds.py -- BluesMinds API (OpenAI-compatible).

Env: BLUESMINDS_KEY (required), BLUESMINDS_MODEL (default gpt-5-chat),
     BLUESMINDS_URL (default https://api.bluesminds.com/v1/chat/completions).
"""
import os
import requests
from .base import Provider


class BluesMindsProvider(Provider):
    name = "bluesminds"

    @property
    def default_model(self):
        return os.getenv("BLUESMINDS_MODEL", "gpt-5-chat")

    def available(self) -> bool:
        return bool(os.getenv("BLUESMINDS_KEY", ""))

    def _map_model(self, model):
        # foreign model names (gpt-4o, gemini, mistral...) -> our default
        if not model or model.startswith(("gpt-4", "o1", "o3", "gemini", "mistral", "llama")):
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
        url = os.getenv("BLUESMINDS_URL",
                        "https://api.bluesminds.com/v1/chat/completions")
        r = requests.post(
            url,
            headers={"Authorization": "Bearer " + os.getenv("BLUESMINDS_KEY", ""),
                     "Content-Type": "application/json"},
            json={"model": self._map_model(model), "messages": messages,
                  "max_tokens": max_tokens, "temperature": temperature},
            timeout=8,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()
