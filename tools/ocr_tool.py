"""OCR tool — extract text from images using pytesseract."""
import os

NAME        = "ocr_tool"
DESCRIPTION = "Extract text from an image file using OCR (Optical Character Recognition)"
CATEGORY    = "builtin"
ICON        = "🔎"
INPUTS = [
    {"name": "image_path", "label": "Image File Path", "type": "text",
     "placeholder": "/path/to/image.png  or  uploads/screenshot.png", "required": True},
    {"name": "lang",       "label": "Language",        "type": "text",
     "placeholder": "eng  (eng, fra, deu, spa, hin, etc.)"},
]


def run(image_path: str, lang: str = "eng") -> dict:
    # Resolve relative paths (relative to project root)
    if not os.path.isabs(image_path):
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        image_path = os.path.join(base, image_path)

    if not os.path.exists(image_path):
        return {"error": f"Image file not found: {image_path}"}

    # ── Primary: pytesseract ──────────────────────────────────────────
    try:
        import pytesseract
        from PIL import Image

        img  = Image.open(image_path)
        text = pytesseract.image_to_string(img, lang=lang or "eng").strip()
        if not text:
            return {"message": "No text detected in the image."}
        return {"message": f"**Extracted Text (OCR):**\n\n{text}"}

    except ImportError:
        pass   # fall through to next method

    # ── Fallback: Pillow only (basic, no real OCR) ───────────────────
    try:
        from PIL import Image
        img = Image.open(image_path)
        w, h = img.size
        return {
            "message": (
                f"Image loaded: {w}×{h}px\n\n"
                "⚠️ Full OCR requires Tesseract. Install it:\n"
                "1. Download Tesseract from https://github.com/UB-Mannheim/tesseract/wiki\n"
                "2. Run: `pip install pytesseract pillow`\n"
                "3. Set PATH or configure `pytesseract.tesseract_cmd`"
            )
        }
    except Exception as e:
        return {"error": f"Could not open image: {e}"}
