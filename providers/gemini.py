"""providers/gemini.py -- Google Gemini provider."""
import os
import requests
from .base import Provider


class GeminiProvider(Provider):
    name = "gemini"

    @property
    def default_model(self):
        # gemini-1.5-flash was retired (404s). Override with GEMINI_MODEL env.
        return os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    def available(self) -> bool:
        return bool(os.getenv("GEMINI_API_KEY", ""))

    def _generate(self, prompt, system, model, max_tokens, temperature) -> str:
        # GPT model names do not exist on Gemini -- use our default instead
        if not model or model.startswith(("gpt", "o1", "o3")):
            model = self.default_model
        url = ("https://generativelanguage.googleapis.com/v1beta/models/"
               + model + ":generateContent?key=" + os.getenv("GEMINI_API_KEY", ""))
        contents = [{"parts": [{"text": (system + "\n\n" + prompt) if system else prompt}]}]
        r = requests.post(
            url,
            json={"contents": contents,
                  "generationConfig": {"maxOutputTokens": max_tokens,
                                       "temperature": temperature}},
            timeout=30,
        )
        r.raise_for_status()
        return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()

    def vision(self, prompt: str, image_b64: str, mime: str = "image/jpeg",
               max_tokens: int = 900) -> str:
        """Analyze an image (used as vision fallback when GitHub is down)."""
        import os as _os, requests as _rq
        url = ("https://generativelanguage.googleapis.com/v1beta/models/"
               + self.default_model + ":generateContent?key="
               + _os.getenv("GEMINI_API_KEY", ""))
        r = _rq.post(url, json={"contents": [{"parts": [
            {"text": prompt or "Describe this image in detail."},
            {"inline_data": {"mime_type": mime, "data": image_b64}}]}],
            "generationConfig": {"maxOutputTokens": max_tokens}}, timeout=30)
        r.raise_for_status()
        return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
