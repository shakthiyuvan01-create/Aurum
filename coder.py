from ai_brain import ask_ai
from patch_writer import save_patch


def generate_code(idea):
    prompt = f"""

    You are Assist Neo.

    You are improving your own project.

    Task:

    {idea}

    Rules:

    - Modify existing Assist Neo functionality.
    - Do NOT generate example programs.
    - Do NOT generate tutorials.
    - Do NOT generate demo code.
    - Generate a real improvement for an AI assistant.
    - Return only Python code.

    """

    response = ask_ai(prompt)

    if response:

        save_patch(
            idea.replace(" ", "_"),
            response
        )

    return response