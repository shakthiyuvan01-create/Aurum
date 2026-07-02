"""providers/gemini.py -- Google Gemini provider."""
import os
import requests
from .base import Provider


class GeminiProvider(Provider):
    name = "gemini"
    default_model = "gemini-1.5-flash"

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
            timeout=120,
        )
        r.raise_for_status()
        return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
