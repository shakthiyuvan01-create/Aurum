"""providers/openai_provider.py -- OpenAI API provider."""
import os
import requests
from .base import Provider


class OpenAIProvider(Provider):
    name = "openai"
    default_model = "gpt-4o-mini"

    def available(self) -> bool:
        return bool(os.getenv("OPENAI_API_KEY", ""))

    def _generate(self, prompt, system, model, max_tokens, temperature) -> str:
        msgs = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.append({"role": "user", "content": prompt})
        r = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": "Bearer " + os.getenv("OPENAI_API_KEY", ""),
                     "Content-Type": "application/json"},
            json={"model": model, "messages": msgs,
                  "max_tokens": max_tokens, "temperature": temperature},
            timeout=30,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()

    def chat(self, messages, model=None, max_tokens=1500, temperature=0.4):
        import requests as _r
        r = _r.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": "Bearer " + os.getenv("OPENAI_API_KEY", ""),
                     "Content-Type": "application/json"},
            json={"model": model or self.default_model, "messages": messages,
                  "max_tokens": max_tokens, "temperature": temperature},
            timeout=30,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()
