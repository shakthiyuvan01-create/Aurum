from ai_brain import ask_ai
from patch_writer import save_patch


def generate_code(idea):

    prompt = f"""

You are Assist Neo.

Generate a Python file to accomplish:

{idea}

Return ONLY Python code.

"""

    response = ask_ai(prompt)

    if response:

        save_patch(
            idea.replace(" ", "_"),
            response
        )

    return response