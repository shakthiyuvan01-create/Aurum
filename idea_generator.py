from ai_brain import ask_ai


def generate_ideas():

    prompt = """
You are Assist Neo.

Review yourself.

Suggest five improvements.

Return only one idea per line.
"""

    response = ask_ai(prompt)

    if not response:
        return []

    ideas = []

    for line in response.split("\n"):

        line = line.strip()

        if len(line) > 5:

            ideas.append(line)

    return ideas