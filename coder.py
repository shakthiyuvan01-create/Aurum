from ai_brain import ask_ai
from patch_writer import save_patch
from self_scanner import read_files

def generate_code(idea):
    project_code = read_files()

    prompt = f"""

    You are Assist Neo.

    You are improving your own project.

    Current project files:

    {project_code}

    Task:

    {idea}

    Rules:

    - Read the existing code.
    - Modify existing functionality.
    - Do NOT invent classes that don't exist.
    - Do NOT create example programs.
    - Do NOT create tutorials.
    - Make small improvements.
    Return ONLY the code changes needed.

Do NOT rewrite the entire file.

Show only the modified functions.

Keep unchanged code out of the response.

    """
    response = ask_ai(prompt)
    if response:
        response = response.replace("```python", "")

        response = response.replace("```", "")

        response = response.strip()

    if response:

        save_patch(
            idea.replace(" ", "_"),
            response
        )

    return response