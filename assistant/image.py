"""assistant/image.py — Image generation with multi-provider support.

Enhanced with the Hermes-style provider-based system (image_gen/).
Falls back to the original Pollinations-only method if the new system fails.
"""
import logging
import os
import time
import urllib.parse
from typing import Optional

import requests as _requests

from assistant.config import IMAGE_SAVE_FOLDER
from assistant.speech import say

log = logging.getLogger("assistant.image")

_last_image_prompt = ""


def create_image(prompt: str, provider: Optional[str] = None, **kwargs) -> Optional[str]:
    """Generate an image using the best available provider.

    Uses the new multi-provider image_gen system. Falls back to original
    Pollinations-only method if new system fails.

    Args:
        prompt: Text description of the image
        provider: Preferred provider name ("pollinations", "openai", "fal", etc.)
        **kwargs: Additional options (aspect_ratio, model, etc.)

    Returns:
        Path to the generated image, or None on failure.
    """
    try:
        from image_gen.tool import generate_image
        save_dir = kwargs.pop("save_dir", IMAGE_SAVE_FOLDER)
        result = generate_image(
            prompt=prompt,
            provider=provider,
            save_dir=save_dir,
            **kwargs,
        )
        if result.get("success") and result.get("image"):
            path = result["image"]
            # If it's already a local file path, return it
            if os.path.exists(path):
                return path
            return path
        # Fall through to legacy method
        log.warning("New image gen failed (%s), falling back to Pollinations", result.get("error"))
    except Exception as e:
        log.debug("New image gen error: %s, falling back to legacy", e)

    # Legacy fallback
    return _legacy_create_image(prompt)


def _legacy_create_image(prompt: str) -> Optional[str]:
    """Original Pollinations-only image generation (fallback)."""
    os.makedirs(IMAGE_SAVE_FOLDER, exist_ok=True)
    out = os.path.join(IMAGE_SAVE_FOLDER, f"image_{int(time.time())}.png")
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    urls = [
        "https://image.pollinations.ai/prompt/" + urllib.parse.quote(prompt)
            + f"?width=1024&height=1024&nologo=true&seed={int(time.time())}",
        "https://image.pollinations.ai/prompt/" + urllib.parse.quote(prompt)
            + "?model=flux&width=1024&height=1024&nologo=true",
        "https://image.pollinations.ai/prompt/" + urllib.parse.quote(prompt),
    ]
    for url in urls:
        try:
            r = _requests.get(url, headers=headers, timeout=120)
            if r.status_code == 200 and len(r.content) > 1000:
                with open(out, "wb") as f:
                    f.write(r.content)
                return out
        except Exception as e:
            log.warning("Image gen error: %s", e)
    return None


def _fuzzy_fix(text: str) -> str:
    corrections = {
        "creat":"create","crate":"create","ceate":"create",
        "generat":"generate","generete":"generate","gnerate":"generate",
        "imge":"image","iamge":"image","imgae":"image","imag":"image",
        "pictur":"picture","pictue":"picture","picter":"picture",
        "mak":"make","maek":"make","drwa":"draw","drow":"draw",
    }
    return " ".join(corrections.get(w, w) for w in text.split())


def handle_images(text: str) -> bool:
    global _last_image_prompt
    low = _fuzzy_fix(text.lower().strip())
    triggers = [
        "create an image of","create image of","create a image of",
        "generate an image of","generate image of","generate a image of",
        "draw","draw me","make an image of","make a image of","make image of",
        "can you create an image of","can you draw","can you generate",
        "show me an image of","show me a image of",
        "create picture of","make a picture of","generate a picture of",
        "image of","picture of",
    ]
    for t in triggers:
        if t in low:
            prompt = low.split(t, 1)[1].strip() or "robot"
            _last_image_prompt = prompt
            img = create_image(prompt)
            say(f"[IMAGE]{img}" if img else "Image creation failed.")
            return True

    edit_triggers = [
        "make it","change it","change the","put the","make the",
        "add","remove","set the","color it","colour it",
        "now make","now change","now add","but","instead",
    ]
    if _last_image_prompt and any(low.startswith(t) or t in low for t in edit_triggers):
        new_prompt = _last_image_prompt + ", " + low
        _last_image_prompt = new_prompt
        img = create_image(new_prompt)
        say(f"[IMAGE]{img}" if img else "Image creation failed.")
        return True
    return False
