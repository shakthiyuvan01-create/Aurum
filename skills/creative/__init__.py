"""Image Generation skill — generate images via text prompts."""
from skills import Skill


def _execute(prompt: str, **kwargs) -> dict:
    from assistant.image import create_image
    path = create_image(prompt, **kwargs)
    if path:
        return {"success": True, "image": path, "prompt": prompt}
    return {"success": False, "error": "Image generation failed", "prompt": prompt}


def register_skill(registry):
    registry.register(Skill(
        name="generate_image",
        description="Generate an image from a text prompt using AI",
        execute=_execute,
        category="creative",
    ))
