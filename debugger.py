from ai_brain import ask_ai


def fix_error(error_message):

    prompt = f"""
You are Assist Neo.

The following error occurred:

{error_message}

Explain the problem and suggest a fix.
Return only the solution.
"""

    response = ask_ai(prompt)

    return response