from ai_brain import ask_ai


def design(idea):

    prompt = f"""
Task:

{idea}

Describe the modules and files needed.

Keep it short.
"""

    response = ask_ai(prompt)

    return response