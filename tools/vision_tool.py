"""Vision tool — analyze images using GPT-4o vision or Ollama llava."""
import os, base64, json, logging
import requests as _rq

log = logging.getLogger(__name__)

NAME        = "vision_tool"
DESCRIPTION = ("Analyze or describe an image. Pass an image file path or a URL. "
               "Use this when the user uploads an image, asks what is in a photo, "
               "or wants to analyze a screenshot.")
CATEGORY    = "builtin"
ICON        = "🖼️"
INPUTS = [
    {"name": "image_path", "label": "Image path or URL", "type": "text",
     "placeholder": "uploads/photo.png  or  https://example.com/img.jpg", "required": True},
    {"name": "question",   "label": "Question about the image", "type": "text",
     "placeholder": "What is in this image?"},
]

GITHUB_API   = "https://models.inference.ai.azure.com/chat/completions"
VISION_MODEL = "gpt-4o"
OLLAMA_API   = os.environ.get("OLLAMA_URL", "http://localhost:11434") + "/api/chat"
OLLAMA_VIS   = "llava"   # vision model in Ollama


def _b64(path: str) -> tuple[str, str]:
    """Return (base64_string, mime_type) for a local image file."""
    ext = os.path.splitext(path)[1].lower()
    mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
            "gif": "image/gif", "webp": "image/webp"}.get(ext.lstrip("."), "image/jpeg")
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode(), mime


def _resolve(image_path: str) -> str:
    """Resolve relative paths to absolute (relative to project root)."""
    if image_path.startswith("http://") or image_path.startswith("https://"):
        return image_path
    if not os.path.isabs(image_path):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        image_path = os.path.join(root, image_path)
    return image_path


def run(image_path: str, question: str = "What is in this image?") -> dict:
    image_path = _resolve(image_path)
    question   = question.strip() or "What is in this image? Describe it in detail."

    token = os.environ.get("GITHUB_TOKEN", "")

    # ── Build image content block ─────────────────────────────────────────────
    if image_path.startswith("http"):
        img_block = {"type": "image_url", "image_url": {"url": image_path}}
    else:
        if not os.path.exists(image_path):
            return {"error": f"Image not found: {image_path}"}
        b64, mime = _b64(image_path)
        data_url  = f"data:{mime};base64,{b64}"
        img_block = {"type": "image_url", "image_url": {"url": data_url}}

    # ── Try GitHub Models (GPT-4o vision) ─────────────────────────────────────
    if token and token.strip() and token != "your_github_token_here":
        payload = {
            "model": VISION_MODEL,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": question},
                    img_block,
                ]
            }],
            "max_tokens": 800,
        }
        try:
            r = _rq.post(GITHUB_API,
                         headers={"Authorization": f"Bearer {token}",
                                  "Content-Type": "application/json"},
                         json=payload, timeout=60)
            r.raise_for_status()
            answer = r.json()["choices"][0]["message"]["content"]
            return {"message": answer}
        except Exception as e:
            log.error("GPT-4o vision error: %s", e)
            if "401" not in str(e) and "403" not in str(e):
                return {"error": f"Vision API error: {e}"}
            log.warning("GPT-4o vision auth failed, falling back to Ollama llava")
            # fall through to Ollama

    # ── Fallback: Ollama llava ────────────────────────────────────────────────
    try:
        # Ollama /api/chat with images list (base64, no data-url prefix)
        if image_path.startswith("http"):
            import urllib.request as _ur
            tmp = "/tmp/_vision_tmp.jpg"
            _ur.urlretrieve(image_path, tmp)
            b64, _ = _b64(tmp)
        else:
            b64, _ = _b64(image_path)

        ollama_payload = {
            "model": OLLAMA_VIS,
            "messages": [{
                "role": "user",
                "content": question,
                "images": [b64],
            }],
            "stream": False,
        }
        r2 = _rq.post(OLLAMA_API, json=ollama_payload, timeout=120)
        r2.raise_for_status()
        answer = r2.json()["message"]["content"]
        return {"message": f"*(via llava)* {answer}"}

    except Exception as e2:
        log.error("Ollama llava vision failed: %s", e2)
        return {"error": f"Vision unavailable. GitHub token missing/expired and Ollama llava failed: {e2}"}
