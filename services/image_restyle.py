"""
services/image_restyle.py -- turn an uploaded image into a styled version.

Not pixel img2img (that needs a paid model). Instead: the vision model
describes the image in detail, then the image generator recreates that scene
in the requested style. Best results for "Ghibli / anime / cartoon / oil
painting" style conversions.
"""
import base64
import logging
import os
import tempfile

log = logging.getLogger("services.image_restyle")

STYLES = {
    "ghibli": ("Studio Ghibli anime style, hand-painted, soft watercolor "
               "backgrounds, warm lighting, Hayao Miyazaki aesthetic, "
               "whimsical, detailed nature, cel shading"),
    "anime":  "anime style, vibrant, clean linework, cel shaded",
    "cartoon": "cartoon style, bold outlines, flat bright colors",
    "oil":    "oil painting, thick brush strokes, classical, textured canvas",
    "pixar":  "3D Pixar animation style, soft rounded, cinematic lighting",
    "sketch": "detailed pencil sketch, black and white, cross-hatching",
    "cyberpunk": "cyberpunk style, neon lights, futuristic, high contrast",
}


def _describe(image_b64: str, mime: str = "image/jpeg") -> str:
    """Vision-describe the image so we can regenerate it."""
    import os as _os, requests as _rq
    token = _os.getenv("GITHUB_TOKEN", "")
    if token:
        try:
            r = _rq.post(
                "https://models.inference.ai.azure.com/chat/completions",
                headers={"Authorization": "Bearer " + token,
                         "Content-Type": "application/json"},
                json={"model": _os.getenv("VISION_MODEL", "gpt-4o"),
                      "max_tokens": 250,
                      "messages": [{"role": "user", "content": [
                          {"type": "text", "text":
                           "Describe this image for an artist to recreate it: "
                           "main subject, composition, colors, mood, background. "
                           "Be concrete and visual in 3-4 sentences."},
                          {"type": "image_url", "image_url": {
                              "url": "data:%s;base64,%s" % (mime, image_b64)}}]}]},
                timeout=45)
            if r.status_code == 200:
                return r.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            log.warning("vision describe failed: %s", e)
    # fallback: Gemini vision via provider
    try:
        from providers.gemini import GeminiProvider
        g = GeminiProvider()
        if g.available():
            return g.vision("Describe this image for an artist to recreate it "
                            "(subject, colors, mood, background), 3-4 sentences.",
                            image_b64, mime=mime, max_tokens=250)
    except Exception as e:
        log.debug("gemini describe failed: %s", e)
    return ""


def restyle(image_b64: str, style: str = "ghibli", mime: str = "image/jpeg") -> dict:
    style = (style or "ghibli").lower().strip()
    style_prompt = STYLES.get(style, STYLES["ghibli"])
    desc = _describe(image_b64, mime)
    if not desc:
        return {"error": "could not read the image (no vision backend). "
                         "Set GITHUB_TOKEN or GEMINI_API_KEY."}
    prompt = "%s. Rendered in %s" % (desc, style_prompt)
    try:
        from assistant.image import create_image
        path = create_image(prompt)
        if not path:
            return {"error": "image generation failed, try again"}
        # serve via /uploads: move into the uploads dir
        import shutil, uuid
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        updir = os.path.join(base, "uploads")
        os.makedirs(updir, exist_ok=True)
        name = "restyle_%s.png" % uuid.uuid4().hex[:10]
        shutil.copy2(path, os.path.join(updir, name))
        return {"ok": True, "style": style, "description": desc,
                "url": "/uploads/" + name}
    except Exception as e:
        log.error("restyle failed: %s", e)
        return {"error": str(e)}
