from ai_brain import ask_ai
from patch_writer import save_patch


def generate_code(idea):
    prompt = f"""
    You are Assist Neo.

    You are improving your own project.

    Current files include:

    assistant.py
    memory_manager.py
    evolution_worker.py
    logger_agent.py
    health_agent.py
    github_agent.py

    Task:

    {idea}

    Rules:

    Modify existing functionality.

    Do NOT create a new AssistNeo class.

    Do NOT create example programs.

    Do NOT create tutorials.

    Prefer improving:

    assistant.py
    logger_agent.py
    memory_manager.py
    evolution_worker.py

    Return ONLY Python code.
    """

    response = ask_ai(prompt)

    if response:

        save_patch(
            idea.replace(" ", "_"),
            response
        )

    return response