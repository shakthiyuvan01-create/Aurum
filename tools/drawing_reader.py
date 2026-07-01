"""
tools/drawing_reader.py — Engineering Drawing Reader.
Analyse single-line diagrams, AutoCAD exports, electrical layouts,
schematics using GPT-4o Vision. Explain components and answer questions.
"""
import base64, logging, os
from pathlib import Path

log = logging.getLogger(__name__)

NAME        = "drawing_reader"
DESCRIPTION = (
    "Read and analyse engineering drawings: single-line diagrams, AutoCAD exports, "
    "electrical layouts, P&IDs, schematics. Explains components, identifies issues, "
    "answers questions. Actions: explain, identify_components, check_compliance, qa."
)
CATEGORY = "engineering"
ICON     = "📐"
INPUTS = [
    {"name": "action",    "label": "Action", "type": "select",
     "options": ["explain","identify_components","check_compliance","qa","describe"],
     "required": True},
    {"name": "image_path","label": "Image file path or URL", "type": "text", "required": True},
    {"name": "question",  "label": "Question (for Q&A)",     "type": "text"},
    {"name": "drawing_type","label": "Drawing type",         "type": "select",
     "options": ["single_line","schematic","layout","autocad","pid","ladder","pcb","general"]},
    {"name": "standard", "label": "Standard to check (e.g. IEC, IS)", "type": "text"},
    {"name": "username", "label": "Username",                "type": "text"},
]

_SYSTEM = """You are an expert electrical engineer with deep knowledge of:
- Single-line diagrams (SLDs) — power distribution, protection schemes
- Electrical schematics — control circuits, relay logic
- AutoCAD electrical drawings — symbols, annotations, bill of materials
- P&ID diagrams — process and instrumentation
- Ladder diagrams — PLC programming

Analyse the provided drawing with precision. Identify:
- Components and their ratings/specifications
- Protection devices (fuses, breakers, relays, CTs, PTs)
- Power flow direction
- Bus bars, switchgear, transformers, capacitors
- Any visible faults, non-standard connections, or safety concerns

Use technical terminology appropriate for a power engineer."""


def _encode_image(image_path: str) -> tuple[str, str]:
    """Return (base64_data, media_type) for a local image."""
    ext = Path(image_path).suffix.lower()
    mt  = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
           "gif": "image/gif",  "bmp": "image/bmp",   "webp": "image/webp"}.get(ext.lstrip("."), "image/png")
    with open(image_path, "rb") as f:
        data = base64.b64encode(f.read()).decode()
    return data, mt


def _vision_ai(image_path: str, prompt: str) -> str:
    token = os.getenv("GITHUB_TOKEN","")
    if not token:
        return "[GITHUB_TOKEN not set]"
    try:
        import requests

        if image_path.startswith("http"):
            # URL image
            messages = [{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": image_path}},
                    {"type": "text",      "text": prompt},
                ],
            }]
        else:
            if not os.path.exists(image_path):
                return f"[File not found: {image_path}]"
            data, mt = _encode_image(image_path)
            messages = [{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:{mt};base64,{data}"}},
                    {"type": "text",      "text": prompt},
                ],
            }]

        r = requests.post(
            "https://models.inference.ai.azure.com/chat/completions",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={
                "model":      "gpt-4o",
                "messages":   [{"role":"system","content":_SYSTEM}] + messages,
                "max_tokens": 1500,
                "temperature": 0.2,
            },
            timeout=120,
        )
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"].strip()
        return f"[Vision API error {r.status_code}: {r.text[:200]}]"
    except Exception as e:
        return f"[Exception: {e}]"


_ACTION_PROMPTS = {
    "explain": (
        "Provide a comprehensive explanation of this engineering drawing. Include:\n"
        "1. Drawing type and purpose\n"
        "2. Main components and their functions\n"
        "3. System overview (voltage levels, power flow)\n"
        "4. Protection scheme (if visible)\n"
        "5. Any notable features or anomalies"
    ),
    "identify_components": (
        "List ALL components visible in this drawing with:\n"
        "- Component name and symbol\n"
        "- Quantity\n"
        "- Ratings/specifications (if shown)\n"
        "- Location/designation\n"
        "Format as a structured table."
    ),
    "check_compliance": (
        "Review this drawing for compliance and best practices:\n"
        "1. Are symbols standard (IEC 60617 / IEEE / IS)?\n"
        "2. Are protection devices adequate?\n"
        "3. Any missing protection, earthing, or interlocks?\n"
        "4. Safety concerns?\n"
        "5. Recommendations for improvement."
    ),
    "describe": (
        "Describe every visible detail in this engineering drawing in clear technical language. "
        "Be thorough — include all text, numbers, symbols, and connections visible."
    ),
}


def run(
    action:       str = "explain",
    image_path:   str = "",
    question:     str = "",
    drawing_type: str = "general",
    standard:     str = "",
    username:     str = "",
) -> dict:
    action = (action or "explain").lower().strip()

    if not image_path:
        return {"error": "image_path required"}

    if action == "qa":
        if not question:
            return {"error": "question required for Q&A"}
        prompt = (
            f"Drawing type: {drawing_type}\n"
            f"Standard context: {standard or 'IEC/IS'}\n\n"
            f"Answer this question about the drawing:\n{question}"
        )
    elif action in _ACTION_PROMPTS:
        prompt = _ACTION_PROMPTS[action]
        if standard:
            prompt += f"\n\nApply {standard} standards."
        if drawing_type != "general":
            prompt = f"Drawing type: {drawing_type}\n\n" + prompt
    else:
        prompt = f"Analyse this {drawing_type} engineering drawing and provide detailed technical insights."

    result = _vision_ai(image_path, prompt)
    return {
        "result":    result,
        "action":    action,
        "image":     image_path,
        "drawing_type": drawing_type,
    }
