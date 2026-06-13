from ai_brain import ask_ai


def think():

    prompt = """
You are the CEO of Assist Neo.

Suggest 5 important improvements.

Return one idea per line.
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